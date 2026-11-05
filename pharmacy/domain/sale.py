from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from pharmacy.domain.pricing import PricingPolicy, StandardPricing
from pharmacy.foundation.contracts import ensure, invariant, keeps_invariant, require

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
    pricing: PricingPolicy = field(default_factory=StandardPricing, repr=False)

    @property
    def subtotal(self) -> Decimal:
        return sum((line.amount for line in self.lines), Decimal("0"))

    def check_invariant(self) -> None:
        invariant(self.total >= 0, "Сума чека не може бути від'ємною")
        invariant(self.total == self.pricing.amount_due(self.subtotal),
                  "Сума чека має відповідати позиціям і способу ціноутворення")

    @keeps_invariant
    def add_line(self, batch: Batch, quantity: int) -> SaleLine:
        require(not any(line.batch is batch for line in self.lines),
                f"Партія {batch.series} вже є в чеку {self.number}")
        require(self.prescription is not None or not batch.drug.requires_prescription,
                "Рецептурний препарат продається лише за е-рецептом")
        lines_before = len(self.lines)
        batch.write_off_sold(quantity, self.sold_at.date())
        line = SaleLine(quantity, batch.retail_price, self, batch)
        self.lines.append(line)
        self.total = self.pricing.amount_due(self.subtotal)
        ensure(len(self.lines) == lines_before + 1, "до чека додано одну позицію")
        return line

    def complete(self) -> None:
        require(bool(self.lines), "Чек має містити щонайменше одну позицію")


@dataclass(eq=False)
class SaleLine:
    quantity: int
    unit_price: Decimal
    sale: Sale
    batch: Batch

    def __post_init__(self) -> None:
        invariant(self.quantity >= 1, "Кількість у позиції має бути додатною")

    @property
    def amount(self) -> Decimal:
        return self.unit_price * self.quantity
