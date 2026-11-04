"""Контролер UC2 «Зарезервувати препарат» (ЛР 5)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pharmacy.domain import (
    MAX_ACTIVE_RESERVATIONS, MAX_RESERVATION_QUANTITY, MIN_RESERVATION_QUANTITY,
    Batch, Customer, EPrescription, Reservation, ReservationState,
)
from pharmacy.foundation.clock import Clock, system_clock
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
        now = self.clock()
        today = now.date()
        if not MIN_RESERVATION_QUANTITY <= quantity <= MAX_RESERVATION_QUANTITY:
            raise Refused("4a", f"Можна резервувати від {MIN_RESERVATION_QUANTITY} "
                                f"до {MAX_RESERVATION_QUANTITY} упаковок")
        customer = self._customer(phone)
        if len(customer.active_reservations) >= MAX_ACTIVE_RESERVATIONS:
            raise Refused("3a", f"Покупець уже має {MAX_ACTIVE_RESERVATIONS} активні резервування")
        batch = self._pick_batch(pharmacy_number, trade_name, quantity, today)
        recipe = self._check_recipe(batch, recipe_number, today)

        code = f"R-{self.store.next_number('reservation')}"
        reservation = Reservation(code, now, quantity, customer, batch, recipe)
        reservation.confirm()
        if reservation.state is ReservationState.CANCELLED:
            raise Refused("5a", f"Партія {batch.series}: залишку вже недостатньо")
        self.store.save_customer(customer)
        self.store.save_reservation(reservation)
        self.store.commit()
        return ReservationResult(code, batch.drug.trade_name, batch.series, quantity, reservation.expires_at)

    def _customer(self, phone: str) -> Customer:
        return self.store.find_customer(phone) or Customer(phone, "")

    def _pick_batch(self, pharmacy_number: str, trade_name: str, quantity: int, today: date) -> Batch:
        suitable = [b for b in self.store.find_batches(pharmacy_number, trade_name)
                    if b.has_shelf_life_for_reservation(today) and b.available >= quantity]
        if not suitable:
            raise Refused("5a", f"В аптеці {pharmacy_number} немає придатної партії препарату {trade_name}")
        return min(suitable, key=lambda b: b.expiry_date)

    def _check_recipe(self, batch: Batch, number: str | None, today: date) -> EPrescription | None:
        if not batch.drug.requires_prescription:
            return None
        if number is None:
            raise Refused("6a", "Для рецептурного препарату потрібен номер е-рецепта")
        recipe = self.registry.find(number)
        if recipe is None or not recipe.is_valid(today) or recipe.inn != batch.drug.inn:
            raise Refused("6b", f"Рецепт {number} не підходить для цього препарату")
        return recipe
