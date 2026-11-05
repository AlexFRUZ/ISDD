from __future__ import annotations

from pharmacy.controllers.sales.common import SaleResult, pharmacist_with
from pharmacy.domain import OtcDrug, PaymentMethod, Sale
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure, require
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


class OtcSaleController:
    def __init__(self, uow: UnitOfWork, clock: Clock = system_clock) -> None:
        self.uow = uow
        self.clock = clock

    def sell(self, pharmacist_number: str, trade_name: str, quantity: int,
             payment: str = "картка") -> SaleResult:
        require(quantity >= 1, "Кількість має бути додатною")
        now = self.clock()
        with self.uow.transaction():
            pharmacist = pharmacist_with(self.uow, pharmacist_number)
            drug = self.uow.drugs.get(trade_name)
            if drug is None:
                raise Refused("3a", f"Препарат {trade_name} не знайдено")
            if not isinstance(drug, OtcDrug):
                raise Refused("3b", f"Препарат {trade_name} є рецептурним")
            if quantity > drug.check_limit:
                raise Refused("4a", f"За один продаж дозволено не більше {drug.check_limit} уп.")
            batch = pharmacist.pharmacy.pick_batch_for_trade_name(trade_name, quantity, now.date())
            if batch is None:
                raise Refused("5a", f"В аптеці немає придатної партії {trade_name}")

            stock_before = batch.quantity
            sale = Sale(f"Ч-{self.uow.next_number('sale')}", now, PaymentMethod(payment), pharmacist)
            sale.add_line(batch, quantity)
            sale.complete()
            self.uow.batches.save(batch)
            self.uow.sales.save(sale)
            ensure(batch.quantity == stock_before - quantity, "залишок партії зменшено")
        return SaleResult(sale.number, trade_name, batch.series, quantity, sale.total)
