from __future__ import annotations

from dataclasses import dataclass
from pharmacy.controllers.warehouse.common import DeliveryLine, manager_with
from pharmacy.controllers.warehouse.delivery_validator import DeliveryValidator
from pharmacy.domain import Batch, Delivery
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure, require
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


@dataclass(frozen=True)
class DeliveryResult:
    invoice_number: str
    supplier: str
    pharmacy_number: str
    batches: tuple[tuple[str, str, int], ...]

    @property
    def packs(self) -> int:
        return sum(quantity for _, _, quantity in self.batches)


class ReceiveDeliveryController:

    def __init__(self, uow: UnitOfWork, clock: Clock = system_clock) -> None:
        self.uow = uow
        self.clock = clock
        self.validator = DeliveryValidator(uow)

    def receive(self, manager_number: str, invoice_number: str, supplier_name: str,
                lines: list[DeliveryLine]) -> DeliveryResult:
        require(bool(invoice_number.strip()), "Номер накладної не може бути порожнім")
        require(bool(lines), "Накладна має містити щонайменше одну позицію")
        require(all(line.quantity >= 1 for line in lines), "Кількість у позиції має бути додатною")
        require(all(line.purchase_price >= 0 and line.retail_price >= 0 for line in lines),
                "Ціна не може бути від'ємною")
        today = self.clock().date()
        with self.uow.transaction():
            manager = manager_with(self.uow, manager_number)
            if self.uow.deliveries.get(invoice_number) is not None:
                raise Refused("3a", f"Накладну {invoice_number} уже прийнято")
            supplier = self.uow.suppliers.get(supplier_name)
            if supplier is None:
                raise Refused("3b", f"Постачальника {supplier_name} не знайдено")
            drugs = self.validator.validated_drugs(manager.pharmacy, lines, today)

            batches = [Batch(line.series, line.expiry_date, line.purchase_price, line.retail_price,
                             line.quantity, drugs[line.trade_name], manager.pharmacy) for line in lines]
            delivery = Delivery(invoice_number, today, supplier, batches)
            self.uow.deliveries.save(delivery)
            ensure(all(b in manager.pharmacy.batches for b in batches), "партії додано до залишків аптеки")
        return DeliveryResult(invoice_number, supplier.name, manager.pharmacy.number,
                              tuple((b.drug.trade_name, b.series, b.quantity) for b in batches))
