from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pharmacy.domain import Director, Manager
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


def manager_with(uow: UnitOfWork, number: str) -> Manager:
    manager = uow.managers.get(number)
    if manager is None:
        raise Refused("зв", f"Завідувача аптеки {number} не знайдено")
    return manager


def reader_with(uow: UnitOfWork, number: str) -> Manager | Director:
    user = uow.managers.get(number) or uow.directors.get(number)
    if user is None:
        raise Refused("зв", f"Користувача {number} не знайдено серед завідувачів і директорів")
    return user


@dataclass(frozen=True)
class DeliveryLine:
    trade_name: str
    series: str
    expiry_date: date
    purchase_price: Decimal
    retail_price: Decimal
    quantity: int
