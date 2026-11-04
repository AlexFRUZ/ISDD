"""Партія препарату в аптеці."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from pharmacy.foundation.errors import DomainError

if TYPE_CHECKING:
    from pharmacy.domain.chain import Pharmacy
    from pharmacy.domain.drug import Drug

MIN_SHELF_LIFE_DAYS = 30


@dataclass(eq=False)
class Batch:
    series: str
    expiry_date: date
    purchase_price: Decimal
    retail_price: Decimal
    quantity: int
    drug: Drug
    pharmacy: Pharmacy
    reserved: int = 0

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise DomainError("Кількість у партії не може бути від'ємною")
        if not 0 <= self.reserved <= self.quantity:
            raise DomainError("Зарезервована кількість має бути в межах кількості партії")
        self.drug.batches.append(self)
        self.pharmacy.batches.append(self)

    @property
    def available(self) -> int:
        return self.quantity - self.reserved

    def is_expired(self, today: date) -> bool:
        return self.expiry_date <= today

    def has_shelf_life_for_reservation(self, today: date) -> bool:
        return self.expiry_date - today >= timedelta(days=MIN_SHELF_LIFE_DAYS)

    def block(self, quantity: int) -> None:
        """Блокує кількість під резервування, не змінюючи фізичний залишок."""
        if quantity > self.available:
            raise DomainError(f"Партія {self.series}: доступно лише {self.available} уп.")
        self.reserved += quantity

    def unblock(self, quantity: int) -> None:
        if quantity > self.reserved:
            raise DomainError(f"Партія {self.series}: заблоковано лише {self.reserved} уп.")
        self.reserved -= quantity

    def write_off_sold(self, quantity: int, today: date) -> None:
        """Зменшує фізичний залишок під час продажу."""
        if self.is_expired(today):
            raise DomainError(f"Партія {self.series}: строк придатності минув")
        if quantity > self.available:
            raise DomainError(f"Партія {self.series}: доступно лише {self.available} уп.")
        self.quantity -= quantity
