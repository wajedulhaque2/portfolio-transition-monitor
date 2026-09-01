from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...


class NullNotifier(Notifier):
    def send(self, message: str) -> None:
        return None
