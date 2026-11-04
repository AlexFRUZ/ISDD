"""Лікар та електронний рецепт."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from pharmacy.domain.pricing import PricingPolicy, ReimbursedPricing, StandardPricing
from pharmacy.foundation.contracts import invariant, keeps_invariant, require

PRESCRIPTION_VALID_DAYS = 30


class PrescriptionState(Enum):
    ACTIVE = "активний"
    REDEEMED = "погашений"
    CANCELLED = "скасований"


@dataclass(eq=False)
class Doctor:
    full_name: str
    specialty: str
    prescriptions: list[EPrescription] = field(default_factory=list, repr=False)


@dataclass(eq=False)
class EPrescription:
    number: str
    issued_on: date
    inn: str
    prescribed_quantity: int
    doctor: Doctor
    reimbursement_share: Decimal = Decimal("0")
    state: PrescriptionState = PrescriptionState.ACTIVE

    def __post_init__(self) -> None:
        self.check_invariant()
        self.doctor.prescriptions.append(self)

    def check_invariant(self) -> None:
        invariant(self.prescribed_quantity >= 1, "Призначена кількість має бути додатною")
        invariant(Decimal("0") <= self.reimbursement_share <= Decimal("1"),
                  "Частка реімбурсації має бути в межах від 0 до 1")

    def invalid_reason(self, today: date) -> str | None:
        """Причина недійсності або None для чинного рецепта. Експерт: рецепт знає свій стан."""
        if self.state is not PrescriptionState.ACTIVE:
            return f"стан «{self.state.value}»"
        if self.issued_on > today:
            return "дата виписки ще не настала"
        if today - self.issued_on > timedelta(days=PRESCRIPTION_VALID_DAYS):
            return "минув строк дії"
        return None

    def is_valid(self, today: date) -> bool:
        return self.invalid_reason(today) is None

    def allows_quantity(self, quantity: int) -> bool:
        return quantity <= self.prescribed_quantity

    def matches(self, inn: str, today: date) -> bool:
        return self.is_valid(today) and self.inn == inn

    def pricing_policy(self) -> PricingPolicy:
        """Спосіб ціноутворення визначає рецепт, бо він знає частку реімбурсації."""
        return ReimbursedPricing(self.reimbursement_share) if self.reimbursement_share else StandardPricing()

    @keeps_invariant
    def redeem(self, quantity: int, today: date) -> None:
        require(self.is_valid(today), f"Рецепт {self.number} недійсний")
        require(self.allows_quantity(quantity), f"Рецепт {self.number}: призначено лише {self.prescribed_quantity} уп.")
        self.state = PrescriptionState.REDEEMED
