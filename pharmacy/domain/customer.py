"""Покупець."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from pharmacy.domain.reservation import MAX_ACTIVE_RESERVATIONS, Reservation
from pharmacy.foundation.contracts import invariant, keeps_invariant, require

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch
    from pharmacy.domain.prescription import EPrescription


@dataclass(eq=False)
class Customer:
    phone: str
    full_name: str
    reservations: list[Reservation] = field(default_factory=list, repr=False)

    @property
    def active_reservations(self) -> list[Reservation]:
        return [r for r in self.reservations if r.is_active]

    @property
    def can_reserve(self) -> bool:
        return len(self.active_reservations) < MAX_ACTIVE_RESERVATIONS

    def check_invariant(self) -> None:
        invariant(len(self.active_reservations) <= MAX_ACTIVE_RESERVATIONS,
                  f"Покупець не може мати більше {MAX_ACTIVE_RESERVATIONS} активних резервувань")

    @keeps_invariant
    def create_reservation(self, code: str, now: datetime, quantity: int, batch: Batch,
                           prescription: EPrescription | None = None) -> Reservation:
        """Творець резервування: покупець містить свої резервування."""
        require(self.can_reserve, f"Покупець уже має {MAX_ACTIVE_RESERVATIONS} активні резервування")
        return Reservation(code, now, quantity, self, batch, prescription)
