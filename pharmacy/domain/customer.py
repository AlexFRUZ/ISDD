"""Покупець."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pharmacy.domain.reservation import Reservation


@dataclass(eq=False)
class Customer:
    phone: str
    full_name: str
    reservations: list[Reservation] = field(default_factory=list, repr=False)

    @property
    def active_reservations(self) -> list[Reservation]:
        return [r for r in self.reservations if r.is_active]
