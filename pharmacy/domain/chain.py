"""Мережа аптек, аптека й фармацевт."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pharmacy.foundation.errors import DomainError

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch


# eq=False: об'єкти предметної області порівнюють за ідентичністю, а не за полями.
@dataclass(eq=False)
class Pharmacy:
    number: str
    address: str
    city: str
    phone: str
    schedule: str
    batches: list[Batch] = field(default_factory=list, repr=False)
    pharmacists: list[Pharmacist] = field(default_factory=list, repr=False)


@dataclass(eq=False)
class PharmacyChain:
    name: str
    edrpou: str
    pharmacies: list[Pharmacy]

    def __post_init__(self) -> None:
        if not self.pharmacies:
            raise DomainError("Мережа має складатися щонайменше з однієї аптеки")

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
