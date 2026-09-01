# Configuration Reference

The public template ships with an illustrative portfolio so the application can validate and test immediately. Replace the example values before connecting live account data.

This document describes the three strategy files:

```text
config/portfolio.yaml
config/thresholds.yaml
config/symbols.yaml
```

> [!IMPORTANT]
> These files describe **your own strategy**. The project does not provide investment advice and does not know whether a target or threshold is appropriate for you.

## 1. `portfolio.yaml`

### Account currency

```yaml
account_currency: GBP
```

V1 currently supports GBP account-value/sizing semantics only.

### Hard cash reserve

```yaml
hard_min_cash_gbp: 100
```

A standalone BUY recommendation is rejected if the proposed amount would take cash below this absolute reserve.

### Desired cash target

```yaml
desired_cash_pct: 0.10
```

This must equal the `CASH` target:

```yaml
targets:
  CASH: 0.10
```

### Maximum single transition

```yaml
max_single_transition_pct: 0.015
```

`0.015` means 1.5% of portfolio value.

The deterministic sizing engine also applies its normal/strong tranche formulas, so this value is a ceiling rather than a promised recommendation size.

### Alert cooldown

```yaml
alert_cooldown_hours: 12
```

Equivalent repeated recommendations are fingerprinted and suppressed during the cooldown period.

### Alert validity

```yaml
alert_validity_hours: 4
```

This is strategy metadata for how long a recommendation should be regarded as current. Do not interpret an old alert as a standing order.

### Direct targets

Example:

```yaml
targets:
  AAPL: 0.25
  MSFT: 0.25
  GOOGL: 0.20
  AMZN: 0.20
  CASH: 0.10
```

All targets must total exactly `1.0`.

Direct targets are used for normal BUILD/underweight calculations and direct TRIM/overweight calculations.

A direct target may be `0.0` when your deliberate transition objective is to reduce an existing position gradually to zero. Example:

```yaml
targets:
  OLD_POSITION: 0.0
```

To make that position trim-eligible, also give it a `trim` threshold and a symbol mapping. The trim engine treats a held zero-target position as fully overweight and still applies the normal strength threshold and tranche-size limits. A zero target is **not** an instruction to sell immediately.

A normal BUILD rule requires a **positive** direct target, so a zero-target asset cannot generate a BUY recommendation.

### Groups / sleeves

Groups let multiple individual holdings contribute to one portfolio target.

Example:

```yaml
targets:
  DATA_CENTRES: 0.10
  CASH: 0.10
  OTHER_ASSETS: 0.80

groups:
  DATA_CENTRES:
    - VRT
    - PWR
    - APLD
```

Group members must exist in `symbols.yaml`.

A group target is calculated as the sum of its members' live portfolio weights.

### Soft component targets

A group member can have a preferred component weight without becoming a separate direct target:

```yaml
soft_component_targets:
  VRT: 0.04
  PWR: 0.04
  APLD: 0.02
```

The current engine can use a soft component target for TRIM calculations. A soft target of `0.0` is also valid for a trim-only transition out of a group component.

BUILD candidates currently require a **positive direct target**. Do not put a symbol only inside a group and expect it to generate normal BUILD recommendations.

### Quality rank

Optional descriptive ranking:

```yaml
quality_rank:
  VRT: 1
  PWR: 2
  APLD: 3
```

The current public scoring engine does not directly convert this field into a score. Use it to document your intended preference and keep strategy configuration understandable.

### Biases

Optional human-readable intent:

```yaml
biases:
  AAPL: TRIM
  GOOGL: BUILD
```

These labels are documentation. The current deterministic decision logic is driven by targets, thresholds and `strategic_priority`.

### Strategic priority

```yaml
strategic_priority:
  AAPL: 0.80
  GOOGL: 1.00
```

Values must be between `0.0` and `1.0`.

Priority contributes to BUILD/TRIM scoring but cannot override freshness, target, cash or safety requirements.

## 2. `thresholds.yaml`

A symbol is considered for BUILD only if it appears under `pullback`.

Example:

```yaml
pullback:
  GOOGL:
    watch: 0.05
    review: 0.08
    strong: 0.12
    abnormal_day: 0.12
```

Interpretation:

```text
watch:         5% below 20-day high
review:        8% below 20-day high
strong:       12% below 20-day high
abnormal_day: 12% one-day decline safety threshold
```

The percentages are only trigger/context inputs. Being below target and crossing a raw threshold does not automatically produce a BUY recommendation.

A symbol is considered for TRIM only if it appears under `trim`.

Example:

```yaml
trim:
  AAPL:
    watch: 0.06
    review: 0.10
    strong: 0.15
```

Strength uses the maximum of:

- rebound from 20-day low
- positive 10-day return
- positive 20-day return

Every threshold set must satisfy:

```text
0 <= watch < review < strong <= 1
```

## 3. `symbols.yaml`

Every symbol that appears in pullback/trim rules needs a market-data mapping.

Example:

```yaml
GOOGL:
  trading212: null
  twelve_data: GOOGL
  yahoo: GOOGL
  exchange: NASDAQ
  currency: USD
```

Fields:

- `trading212` — Trading 212 broker ticker used to map the live holding
- `yahoo` — Yahoo chart symbol; current primary market source
- `twelve_data` — optional Twelve Data fallback symbol
- `exchange` — exchange calendar used for freshness checks
- `currency` — market quote currency metadata

Current freshness calendars include:

```text
NYSE
NASDAQ
LSE
```

For London-listed Yahoo symbols, Yahoo often uses a `.L` suffix. Trading 212 broker identifiers can differ substantially from Yahoo/exchange tickers.

### Resolve Trading 212 broker tickers

Start with:

```yaml
trading212: null
```

Then, after configuring read-only credentials:

```bash
portfolio-monitor resolve-symbols
```

Review the suggested YAML carefully.

Only when it is correct:

```bash
portfolio-monitor resolve-symbols --write
```

If a symbol does not resolve automatically, inspect Trading 212 instrument metadata and enter the exact broker ticker manually.

## 4. Adding a new independent target

Suppose you want to add `XYZ` as a 5% direct target.

1. Add it to `symbols.yaml`.
2. Add `XYZ: 0.05` to `portfolio.yaml` targets.
3. Reduce other target(s) so the total remains `1.0`.
4. Set a strategic priority if desired.
5. Add it under `pullback` if it should generate BUILD candidates.
6. Add it under `trim` if it should generate TRIM candidates.
7. Validate and test.

Run:

```bash
portfolio-monitor validate-config
ruff check app tests
mypy app
pytest -q
```

## 5. Transitioning a position to zero

If you currently hold a position that you ultimately want to exit gradually rather than sell immediately:

1. Keep the symbol in `symbols.yaml`.
2. Add it as a direct target with value `0.0`, or use a zero soft-component target for a group member.
3. Add a `trim` threshold.
4. Give it an appropriate `strategic_priority`.
5. Do **not** add it under `pullback`.
6. Run validation and tests.

The monitor can then recommend bounded trims only when the configured strength conditions are met.

## 6. Adding a group member

If the symbol belongs only to a group:

1. Add it to `symbols.yaml`.
2. Add it to the group list in `portfolio.yaml`.
3. Optionally add a `soft_component_targets` value.
4. Add a TRIM threshold if you want the component individually trim-eligible.

Remember: normal BUILD logic currently requires a positive direct target for the symbol.

## 7. Removing a symbol

Before deleting a symbol from `symbols.yaml`, remove or update references in:

- `targets`
- `groups`
- `soft_component_targets`
- `quality_rank`
- `biases`
- `strategic_priority`
- `pullback`
- `trim`

Also confirm the symbol is no longer a live holding you expect the monitor to understand.

Then run configuration validation and tests.

## 8. Example portfolio is not a preset strategy

The included AAPL/MSFT/GOOGL/AMZN configuration exists only to make the public repository self-contained and testable.

Do not infer that:

- these assets are recommended
- these allocations are recommended
- these thresholds fit your risk tolerance
- the application can decide your investment objectives for you

Replace the example configuration with your own deliberate plan before using live data.
