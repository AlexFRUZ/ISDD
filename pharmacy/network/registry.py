"""Шлюз до реєстру е-рецептів.

Реальний реєстр ЕСОЗ у навчальному проєкті замінено локальною реалізацією з тим самим
інтерфейсом. Заміна на справжній клієнт API змінить лише цей пакет.
"""
from __future__ import annotations

from datetime import date
from typing import Protocol

from pharmacy.domain import EPrescription


class RegistryUnavailable(Exception):
    """Реєстр не відповідає."""


class PrescriptionRegistry(Protocol):
    def find(self, number: str) -> EPrescription | None: ...
    def redeem(self, recipe: EPrescription, quantity: int, today: date) -> None: ...


class LocalRegistry:
    def __init__(self, prescriptions: dict[str, EPrescription], online: bool = True) -> None:
        self._prescriptions = prescriptions
        self.online = online

    def find(self, number: str) -> EPrescription | None:
        return self._prescriptions.get(number)

    def redeem(self, recipe: EPrescription, quantity: int, today: date) -> None:
        if not self.online:
            raise RegistryUnavailable
        recipe.redeem(quantity, today)
