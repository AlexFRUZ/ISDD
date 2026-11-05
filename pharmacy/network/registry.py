from __future__ import annotations

from datetime import date
from typing import Protocol

from pharmacy.domain import EPrescription


class RegistryUnavailable(Exception):
    pass


class PrescriptionRegistry(Protocol):
    def find(self, number: str) -> EPrescription | None: ...
    def redeem(self, recipe: EPrescription, quantity: int, today: date) -> None: ...


class PrescriptionSource(Protocol):
    def get(self, key: str) -> EPrescription | None: ...
    def save(self, entity: EPrescription) -> None: ...


class LocalRegistry:
    def __init__(self, prescriptions: PrescriptionSource, online: bool = True) -> None:
        self._prescriptions = prescriptions
        self.online = online

    def find(self, number: str) -> EPrescription | None:
        return self._prescriptions.get(number)

    def redeem(self, recipe: EPrescription, quantity: int, today: date) -> None:
        if not self.online:
            raise RegistryUnavailable
        recipe.redeem(quantity, today)
        self._prescriptions.save(recipe)
