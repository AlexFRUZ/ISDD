from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pharmacy.controllers.warehouse.common import manager_with
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import require
from pharmacy.persistence.repositories import UnitOfWork

EXPIRY_WARNING_DAYS = 30


@dataclass(frozen=True)
class ExpiringBatch:
    trade_name: str
    series: str
    expiry_date: date
    days_left: int
    quantity: int
    reserved: int

    @property
    def expired(self) -> bool:
        return self.days_left <= 0


class ExpiryController:

    def __init__(self, uow: UnitOfWork, clock: Clock = system_clock) -> None:
        self.uow = uow
        self.clock = clock

    def expiring(self, manager_number: str, days: int = EXPIRY_WARNING_DAYS) -> list[ExpiringBatch]:
        require(days >= 0, "Кількість днів не може бути від'ємною")
        today = self.clock().date()
        with self.uow.transaction():
            manager = manager_with(self.uow, manager_number)
            batches = manager.pharmacy.expiring_batches(today, days)
            return [ExpiringBatch(b.drug.trade_name, b.series, b.expiry_date, b.days_until_expiry(today),
                                  b.quantity, b.reserved) for b in batches]
