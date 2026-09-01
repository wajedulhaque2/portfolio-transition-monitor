from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import AlertRecord
from app.db.session import Database
from app.portfolio.calculator import weights
from app.portfolio.models import MarketMetrics, PortfolioState
from app.signals.build import BuildSignal, build_score
from app.signals.rotation import RotationSignal, rotation_score
from app.signals.sizing import buy_size, trim_size
from app.signals.trim import TrimSignal, trim_score


@dataclass(slots=True)
class Recommendation:
    action: str
    buy_symbol: str | None
    sell_symbol: str | None
    amount_gbp: float
    score: float
    tier: str
    reason: str
    manual_review: bool = False


class MonitorEngine:
    def __init__(self, cfg: dict, thresholds: dict):
        self.cfg = cfg
        self.thresholds = thresholds

    def evaluate(
        self, state: PortfolioState, metrics: dict[str, MarketMetrics]
    ) -> list[Recommendation]:
        w = weights(state, self.cfg.get("groups", {}))
        targets = self.cfg["targets"]
        priorities = self.cfg.get("strategic_priority", {})
        positions = {p.symbol: p for p in state.positions}
        builds: list[BuildSignal] = []
        trims: list[TrimSignal] = []

        for sym, th in self.thresholds.get("pullback", {}).items():
            m = metrics.get(sym)
            if not m or sym in state.pending_buy_symbols:
                continue
            target = float(targets.get(sym, 0))
            builds.append(
                build_score(w.get(sym, 0), target, m, th, float(priorities.get(sym, 0.5)))
            )

        for sym, th in self.thresholds.get("trim", {}).items():
            m = metrics.get(sym)
            if not m:
                continue
            target = float(targets.get(sym, self.cfg.get("soft_component_targets", {}).get(sym, 0)))
            pos = positions.get(sym)
            trims.append(
                trim_score(
                    w.get(sym, 0),
                    target,
                    m,
                    th,
                    float(priorities.get(sym, 0.6)),
                    None if not pos else pos.pnl_gbp,
                )
            )

        builds = [x for x in builds if x.tier in {"REVIEW", "STRONG"}]
        trims = [x for x in trims if x.tier in {"REVIEW", "STRONG"}]
        recs: list[Recommendation] = []
        total = state.total_value_gbp
        max_pct = float(self.cfg.get("max_single_transition_pct", 0.015))

        for b in builds:
            target_gap = max(0.0, (float(targets[b.symbol]) - w.get(b.symbol, 0)) * total)
            amount = buy_size(total, target_gap, b.tier == "STRONG", max_pct)
            if amount <= 0:
                continue
            if b.manual_review:
                recs.append(
                    Recommendation(
                        "MANUAL_REVIEW",
                        b.symbol,
                        None,
                        0,
                        b.score,
                        b.tier,
                        "Large one-day drop: verify fundamentals before adding",
                        True,
                    )
                )
                continue
            # Standalone buy only if cash can preserve hard reserve.
            hard_min = float(self.cfg.get("hard_min_cash_gbp", 100))
            if state.cash_gbp - amount >= hard_min:
                recs.append(
                    Recommendation(
                        "BUY",
                        b.symbol,
                        None,
                        amount,
                        b.score,
                        b.tier,
                        "Meaningful pullback while below target",
                    )
                )

        for t in trims:
            target = float(
                targets.get(t.symbol, self.cfg.get("soft_component_targets", {}).get(t.symbol, 0))
            )
            excess = max(0.0, (w.get(t.symbol, 0) - target) * total)
            amount = trim_size(total, excess, t.tier == "STRONG", max_pct)
            if amount > 0:
                recs.append(
                    Recommendation(
                        "TRIM",
                        None,
                        t.symbol,
                        amount,
                        t.score,
                        t.tier,
                        "Overweight position showing strength",
                    )
                )

        for t in trims:
            for b in builds:
                if b.manual_review:
                    continue
                r: RotationSignal = rotation_score(t, b)
                if r.tier not in {"REVIEW", "STRONG"}:
                    continue
                buy_gap = max(0.0, (float(targets[b.symbol]) - w.get(b.symbol, 0)) * total)
                t_target = float(
                    targets.get(
                        t.symbol, self.cfg.get("soft_component_targets", {}).get(t.symbol, 0)
                    )
                )
                excess = max(0.0, (w.get(t.symbol, 0) - t_target) * total)
                amount = min(
                    buy_size(total, buy_gap, r.tier == "STRONG", max_pct),
                    trim_size(total, excess, r.tier == "STRONG", max_pct),
                )
                if amount > 0:
                    recs.append(
                        Recommendation(
                            "ROTATE",
                            b.symbol,
                            t.symbol,
                            amount,
                            r.score,
                            r.tier,
                            "Strong overweight funding source paired with underweight pullback",
                        )
                    )

        # Prefer the best single action per scan; rotations beat equivalent standalone actions.
        recs.sort(key=lambda x: (x.score, 1 if x.action == "ROTATE" else 0), reverse=True)
        return recs


def fingerprint(rec: Recommendation) -> str:
    bucket = int(rec.amount_gbp // 25)
    raw = f"{rec.action}:{rec.sell_symbol}:{rec.buy_symbol}:{rec.tier}:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()


def should_notify(db: Database, rec: Recommendation, cooldown_hours: int) -> bool:
    fp = fingerprint(rec)
    cutoff = datetime.now(UTC) - timedelta(hours=cooldown_hours)
    with db.session() as s:
        last = s.scalar(
            select(AlertRecord)
            .where(AlertRecord.fingerprint == fp)
            .order_by(AlertRecord.created_at.desc())
        )
        if not last:
            return True
        created = last.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return created < cutoff


def record_alert(db: Database, rec: Recommendation, message: str) -> None:
    with db.session() as s:
        s.add(AlertRecord(fingerprint=fingerprint(rec), tier=rec.tier, message=message))
        s.commit()


def format_alert(
    rec: Recommendation,
    state: PortfolioState,
    metrics: dict[str, MarketMetrics],
    dry_run: bool = True,
) -> str:
    lines = ["PORTFOLIO TRANSITION ALERT", ""]
    if rec.action == "ROTATE":
        lines += [f"ROTATE: £{rec.amount_gbp:.0f} {rec.sell_symbol} → {rec.buy_symbol}"]
    elif rec.action == "TRIM":
        lines += [f"TRIM: ~£{rec.amount_gbp:.0f} {rec.sell_symbol}"]
    elif rec.action == "BUY":
        lines += [f"BUY/ADD: ~£{rec.amount_gbp:.0f} {rec.buy_symbol}"]
    else:
        lines += [f"MANUAL REVIEW: {rec.buy_symbol or rec.sell_symbol}"]
    if rec.buy_symbol and rec.buy_symbol in metrics:
        m = metrics[rec.buy_symbol]
        lines += [
            f"{rec.buy_symbol}: {m.current_price:.2f}, pullback {m.pullback_from_20d_high * 100:.1f}% from 20d high"
        ]
    if rec.sell_symbol and rec.sell_symbol in metrics:
        m = metrics[rec.sell_symbol]
        lines += [f"{rec.sell_symbol}: rebound {m.rebound_from_20d_low * 100:.1f}% from 20d low"]
    lines += [
        f"Score: {rec.score:.1f} ({rec.tier})",
        f"Cash: ~£{state.cash_gbp:.0f}",
        f"Reason: {rec.reason}",
    ]
    if rec.manual_review:
        lines += ["Large pullback detected: verify the reason before adding."]
    if dry_run:
        lines += ["", "Advisory only — no automatic trade has been placed."]
    return "\n".join(lines)
