from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from pharmacy.foundation.errors import DomainError

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch


@dataclass(eq=False)
class Pharmacy:
    number: str
    address: str
    city: str
    phone: str
    schedule: str
    batches: list[Batch] = field(default_factory=list, repr=False)
    pharmacists: list[Pharmacist] = field(default_factory=list, repr=False)

    def pick_batch_for_sale(self, inn: str, quantity: int, today: date) -> Batch | None:
        suitable = [b for b in self.batches if b.drug.inn == inn and b.can_supply(quantity, today)]
        return min(suitable, key=lambda b: b.expiry_date, default=None)

    def pick_batch_for_reservation(self, trade_name: str, quantity: int, today: date) -> Batch | None:
        suitable = [b for b in self.batches
                    if b.drug.trade_name == trade_name and b.can_be_reserved(quantity, today)]
        return min(suitable, key=lambda b: b.expiry_date, default=None)


@dataclass(eq=False)
class PharmacyChain:
    name: str
    edrpou: str
    pharmacies: list[Pharmacy]

    def __post_init__(self) -> None:
        if not self.pharmacies:
            raise DomainError("Мережа має складатися щонайменше з однієї аптеки")

    def pharmacies_with(self, inn: str, quantity: int, today: date, excluding: Pharmacy) -> list[Pharmacy]:
        return [p for p in self.pharmacies
                if p is not excluding and p.pick_batch_for_sale(inn, quantity, today) is not None]

    def remove_pharmacy(self, pharmacy: Pharmacy) -> None:
        if len(self.pharmacies) == 1:
            raise DomainError("Не можна видалити останню аптеку мережі")
        self.pharmacies.remove(pharmacy)


@dataclass(eq=False)
class Pharmacist:
    personnel_number: str
    full_name: str
    pharmacy: Pharmacy

    def __post_init__(self) -> None:
        self.pharmacy.pharmacists.append(self)
