"""Постачальник і поставка."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from pharmacy.foundation.errors import DomainError

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch


@dataclass(eq=False)
class Supplier:
    name: str
    phone: str
    deliveries: list[Delivery] = field(default_factory=list, repr=False)


@dataclass(eq=False)
class Delivery:
    invoice_number: str
    delivery_date: date
    supplier: Supplier
    batches: list[Batch]

    def __post_init__(self) -> None:
        if not self.batches:
            raise DomainError("Поставка має містити щонайменше одну партію")
        self.supplier.deliveries.append(self)
