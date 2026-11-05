from __future__ import annotations

from typing import Protocol


class SmsUnavailable(Exception):
    pass


class SmsGateway(Protocol):
    def send(self, phone: str, text: str) -> None: ...


class LocalSmsGateway:
    def __init__(self, online: bool = True) -> None:
        self.online = online
        self.sent: list[tuple[str, str]] = []

    def send(self, phone: str, text: str) -> None:
        if not self.online:
            raise SmsUnavailable
        self.sent.append((phone, text))
