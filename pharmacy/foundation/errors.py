"""Винятки, спільні для всіх рівнів."""
from __future__ import annotations

class DomainError(Exception):
    """Порушення кратності або інваріанта предметної області."""


class TransitionError(DomainError):
    """Подія недопустима в поточному стані або не виконано умову переходу."""


class Refused(Exception):
    """Альтернативний потік варіанта використання: операцію не виконано."""

    def __init__(self, flow: str, message: str) -> None:
        super().__init__(message)
        self.flow = flow


class ContractError(DomainError):
    """Порушення передумови, постумови або інваріанта."""
