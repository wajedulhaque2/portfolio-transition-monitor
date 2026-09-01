from __future__ import annotations

import httpx

from app.notifications.base import Notifier


class TelegramNotifier(Notifier):
    def __init__(
        self,
        token: str,
        chat_id: str,
        timeout: float = 15.0,
    ):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.timeout = timeout

    def send(self, message: str) -> None:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")

        with httpx.Client(
            transport=transport,
            trust_env=False,
            timeout=self.timeout,
        ) as client:
            response = client.post(
                self.url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                },
            )

        response.raise_for_status()