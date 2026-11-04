"""Продаж і його позиції."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from pharmacy.foundation.errors import DomainError

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch
    from pharmacy.domain.chain import Pharmacist
    from pharmacy.domain.customer import Customer
    from pharmacy.domain.prescription import EPrescription


class PaymentMethod(Enum):
    CASH = "готівка"
    CARD = "картка"


@dataclass(eq=False)
class Sale:
    number: str
    sold_at: datetime
    payment_method: PaymentMethod
    pharmacist: Pharmacist
    customer: Customer | None = None
    prescription: EPrescription | None = None
    total: Decimal = Decimal("0")
    lines: list[SaleLine] = field(default_factory=list, repr=False)

    def add_line(self, batch: Batch, quantity: int) -> SaleLine:
        if any(line.batch is batch for line in self.lines):
            raise DomainError(f"Партія {batch.series} вже є в чеку {self.number}")
        today = self.sold_at.date()
        if batch.drug.requires_prescription and self.prescription is None:
            raise DomainError("Рецептурний препарат продається лише за е-рецептом")
        batch.write_off_sold(quantity, today)
        line = SaleLine(quantity, batch.retail_price, self, batch)
        self.lines.append(line)
        self.total += line.amount
        return line

    def complete(self) -> None:
        if not self.lines:
            raise DomainError("Чек має містити щонайменше одну позицію")


@dataclass(eq=False)
class SaleLine:
    """Асоціативний клас зв'язку «Продаж – Партія»."""

    quantity: int
    unit_price: Decimal
    sale: Sale
    batch: Batch

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise DomainError("Кількість у позиції має бути додатною")

    @property
    def amount(self) -> Decimal:
        return self.unit_price * self.quantity
