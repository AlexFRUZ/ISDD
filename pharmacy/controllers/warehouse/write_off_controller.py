from __future__ import annotations

from dataclasses import dataclass

from pharmacy.controllers.warehouse.common import manager_with
from pharmacy.domain import WriteOff, WriteOffReason
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure, require
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


@dataclass(frozen=True)
class WriteOffResult:
    number: str
    trade_name: str
    series: str
    written_off: int
    remaining: int
    reason: str


class WriteOffController:

    def __init__(self, uow: UnitOfWork, clock: Clock = system_clock) -> None:
        self.uow = uow
        self.clock = clock

    def write_off(self, manager_number: str, trade_name: str, series: str, reason: str,
                  quantity: int | None = None) -> WriteOffResult:
        require(quantity is None or quantity >= 1, "Кількість має бути додатною")
        with self.uow.transaction():
            manager = manager_with(self.uow, manager_number)
            batch = self.uow.batches.get((manager.pharmacy.number, trade_name, series))
            if batch is None:
                raise Refused("3a", f"Партії {series} препарату {trade_name} немає в аптеці {manager.pharmacy.number}")
            try:
                reason_value = WriteOffReason(reason)
            except ValueError:
                allowed = ", ".join(r.value for r in WriteOffReason)
                raise Refused("4a", f"Невідома причина «{reason}». Допустимо: {allowed}") from None
            amount = batch.available if quantity is None else quantity
            if batch.quantity == 0:
                raise Refused("5a", f"Партія {series} уже порожня")
            if amount < 1 or amount > batch.available:
                raise Refused("5b", f"Можна списати від 1 до {batch.available} уп. (решта зарезервована)")

            quantity_before = batch.quantity
            batch.write_off(amount)
            record = WriteOff(f"С-{self.uow.next_number('write_off')}", self.clock(), amount,
                              reason_value, batch, manager)
            self.uow.batches.save(batch)
            self.uow.write_offs.save(record)
            ensure(batch.quantity == quantity_before - amount, "залишок партії зменшено")
        return WriteOffResult(record.number, trade_name, series, amount, batch.quantity, reason_value.value)
