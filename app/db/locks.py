from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.models import LockRecord
from app.db.session import Database


def try_acquire_lock(db: Database, name: str = "scan", stale_after_minutes: int = 55) -> bool:
    with db.session() as s:
        row = s.get(LockRecord, name)
        now = datetime.now(UTC)
        if row:
            acquired = row.acquired_at
            if acquired.tzinfo is None:
                acquired = acquired.replace(tzinfo=UTC)
            if now - acquired < timedelta(minutes=stale_after_minutes):
                return False
            s.delete(row)
            s.commit()
        s.add(LockRecord(name=name, acquired_at=now))
        s.commit()
        return True


def release_lock(db: Database, name: str = "scan") -> None:
    with db.session() as s:
        row = s.get(LockRecord, name)
        if row:
            s.delete(row)
            s.commit()
