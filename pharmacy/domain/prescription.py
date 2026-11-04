"""Лікар та електронний рецепт."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from pharmacy.foundation.errors import DomainError

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
        if self.prescribed_quantity < 1:
            raise DomainError("Призначена кількість має бути додатною")
        if not Decimal("0") <= self.reimbursement_share <= Decimal("1"):
            raise DomainError("Частка реімбурсації має бути в межах від 0 до 1")
        self.doctor.prescriptions.append(self)

    def is_valid(self, today: date) -> bool:
        age = today - self.issued_on
        return self.state is PrescriptionState.ACTIVE and age <= timedelta(days=PRESCRIPTION_VALID_DAYS)

    def redeem(self, quantity: int, today: date) -> None:
        if not self.is_valid(today):
            raise DomainError(f"Рецепт {self.number} недійсний")
        if quantity > self.prescribed_quantity:
            raise DomainError(f"Рецепт {self.number}: призначено лише {self.prescribed_quantity} уп.")
        self.state = PrescriptionState.REDEEMED
