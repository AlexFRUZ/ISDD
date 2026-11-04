"""Контролер UC2 «Зарезервувати препарат».

Контролер лише координує кроки: партію добирає аптека, ліміт перевіряє покупець,
а резервування створює покупець, який його містить (шаблони Expert і Creator).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pharmacy.domain import (
    MAX_ACTIVE_RESERVATIONS, MAX_RESERVATION_QUANTITY, MIN_RESERVATION_QUANTITY,
    Batch, Customer, EPrescription, Reservation, ReservationState,
)
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure
from pharmacy.foundation.errors import Refused
from pharmacy.network.registry import PrescriptionRegistry
from pharmacy.persistence.store import Store


@dataclass(frozen=True)
class ReservationResult:
    code: str
    trade_name: str
    series: str
    quantity: int
    expires_at: datetime


class ReservationController:
    def __init__(self, store: Store, registry: PrescriptionRegistry, clock: Clock = system_clock) -> None:
        self.store = store
        self.registry = registry
        self.clock = clock

    def reserve(self, phone: str, pharmacy_number: str, trade_name: str, quantity: int,
                recipe_number: str | None = None) -> ReservationResult:
        """Контракт: lab6/contracts.md, метод 2."""
        now = self.clock()
        today = now.date()
        if not Reservation.is_allowed_quantity(quantity):
            raise Refused("4a", f"Можна резервувати від {MIN_RESERVATION_QUANTITY} "
                                f"до {MAX_RESERVATION_QUANTITY} упаковок")
        customer = self.store.find_customer(phone) or Customer(phone, "")
        if not customer.can_reserve:
            raise Refused("3a", f"Покупець уже має {MAX_ACTIVE_RESERVATIONS} активні резервування")
        batch = self._batch_for(pharmacy_number, trade_name, quantity, today)
        recipe = self._recipe_for(batch, recipe_number, today)
        available_before = batch.available

        code = f"R-{self.store.next_number('reservation')}"
        reservation = customer.create_reservation(code, now, quantity, batch, recipe)
        reservation.confirm()
        self.store.save_customer(customer)
        self.store.save_reservation(reservation)
        self.store.commit()

        ensure(reservation.state is ReservationState.CONFIRMED, "резервування підтверджено")
        ensure(batch.available == available_before - quantity, "доступний залишок зменшено")
        return ReservationResult(code, batch.drug.trade_name, batch.series, quantity, reservation.expires_at)

    def _batch_for(self, pharmacy_number: str, trade_name: str, quantity: int, today: date) -> Batch:
        pharmacy = self.store.find_pharmacy(pharmacy_number)
        batch = pharmacy.pick_batch_for_reservation(trade_name, quantity, today) if pharmacy else None
        if batch is None:
            raise Refused("5a", f"В аптеці {pharmacy_number} немає придатної партії препарату {trade_name}")
        return batch

    def _recipe_for(self, batch: Batch, number: str | None, today: date) -> EPrescription | None:
        if not batch.drug.requires_prescription:
            return None
        if number is None:
            raise Refused("6a", "Для рецептурного препарату потрібен номер е-рецепта")
        recipe = self.registry.find(number)
        if recipe is None or not recipe.matches(batch.drug.inn, today):
            raise Refused("6b", f"Рецепт {number} не підходить для цього препарату")
        return recipe
