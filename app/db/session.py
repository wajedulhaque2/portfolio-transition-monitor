from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


class Database:
    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {
        }
        self.engine = create_engine(
            url, future=True, connect_args=connect_args)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self):
        s: Session = self.Session()
        try:
            yield s
        finally:
            s.close()

    def close(self) -> None:
        self.engine.dispose()
