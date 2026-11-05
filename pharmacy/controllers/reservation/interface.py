from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from pharmacy.domain import EPrescription, Reservation
from pharmacy.foundation.errors import Refused
from pharmacy.network.registry import PrescriptionRegistry
from pharmacy.persistence.repositories import UnitOfWork


class RecipeVerifier(Protocol):
    def verified_for(self, number: str, inn: str, today: date) -> EPrescription: ...


class RegistryRecipeVerifier:
    def __init__(self, registry: PrescriptionRegistry) -> None:
        self.registry = registry

    def verified_for(self, number: str, inn: str, today: date) -> EPrescription:
        recipe = self.registry.find(number)
        if recipe is None or not recipe.matches(inn, today):
            raise Refused("6b", f"Рецепт {number} не підходить для цього препарату")
        return recipe


class ReservationProvider:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def find(self, code: str) -> Reservation | None:
        return self.uow.reservations.get(code)

    def complete_issue(self, reservation: Reservation, moment: datetime) -> None:
        reservation.issue(moment)
        self.uow.batches.save(reservation.batch)
        self.uow.reservations.save(reservation)
