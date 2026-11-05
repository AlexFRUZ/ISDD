from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from pharmacy.foundation.contracts import ensure, invariant, keeps_invariant, require

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
        self.check_invariant()
        self.drug.batches.append(self)
        self.pharmacy.batches.append(self)

    def check_invariant(self) -> None:
        invariant(self.quantity >= 0, "Кількість у партії не може бути від'ємною")
        invariant(0 <= self.reserved <= self.quantity,
                  "Зарезервована кількість має бути в межах кількості партії")

    @property
    def available(self) -> int:
        return self.quantity - self.reserved

    def is_expired(self, today: date) -> bool:
        return self.expiry_date <= today

    def has_shelf_life_for_reservation(self, today: date) -> bool:
        return self.expiry_date - today >= timedelta(days=MIN_SHELF_LIFE_DAYS)

    def can_supply(self, quantity: int, today: date) -> bool:
        return not self.is_expired(today) and self.available >= quantity

    def can_be_reserved(self, quantity: int, today: date) -> bool:
        return self.has_shelf_life_for_reservation(today) and self.available >= quantity

    @keeps_invariant
    def block(self, quantity: int) -> None:
        require(quantity > 0, "Кількість має бути додатною")
        require(quantity <= self.available, f"Партія {self.series}: доступно лише {self.available} уп.")
        available_before = self.available
        self.reserved += quantity
        ensure(self.available == available_before - quantity, "доступний залишок зменшено на кількість")

    @keeps_invariant
    def unblock(self, quantity: int) -> None:
        require(quantity > 0, "Кількість має бути додатною")
        require(quantity <= self.reserved, f"Партія {self.series}: заблоковано лише {self.reserved} уп.")
        self.reserved -= quantity

    @keeps_invariant
    def write_off_sold(self, quantity: int, today: date) -> None:
        require(quantity > 0, "Кількість має бути додатною")
        require(not self.is_expired(today), f"Партія {self.series}: строк придатності минув")
        require(quantity <= self.available, f"Партія {self.series}: доступно лише {self.available} уп.")
        self.quantity -= quantity
