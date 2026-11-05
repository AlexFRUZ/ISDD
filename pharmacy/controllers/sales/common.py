from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pharmacy.domain import Pharmacist
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


@dataclass(frozen=True)
class SaleResult:
    number: str
    trade_name: str
    series: str
    quantity: int
    total: Decimal


def pharmacist_with(uow: UnitOfWork, number: str) -> Pharmacist:
    pharmacist = uow.pharmacists.get(number)
    if pharmacist is None:
        raise Refused("пм", f"Фармацевта {number} не знайдено")
    return pharmacist
