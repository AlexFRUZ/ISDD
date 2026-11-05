from __future__ import annotations

from datetime import date

from pharmacy.controllers.sales.common import SaleResult, pharmacist_with
from pharmacy.controllers.sales.verification import PrescriptionVerificationService
from pharmacy.domain import Batch, EPrescription, PaymentMethod, PrescriptionState, Sale
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure, require
from pharmacy.foundation.errors import Refused
from pharmacy.network.registry import PrescriptionRegistry
from pharmacy.persistence.repositories import UnitOfWork


class PrescriptionSaleController:
    def __init__(self, uow: UnitOfWork,
                 verifier: PrescriptionVerificationService | PrescriptionRegistry,
                 clock: Clock = system_clock) -> None:
        self.uow = uow
        self.verifier = (verifier if isinstance(verifier, PrescriptionVerificationService)
                         else PrescriptionVerificationService(verifier))
        self.clock = clock

    def sell(self, pharmacist_number: str, recipe_number: str, quantity: int,
             payment: str = "картка") -> SaleResult:
        require(quantity >= 1, "Кількість має бути додатною")
        now = self.clock()
        today = now.date()
        with self.uow.transaction():
            pharmacist = pharmacist_with(self.uow, pharmacist_number)
            recipe = self._valid_recipe(recipe_number, today)
            if not recipe.allows_quantity(quantity):
                raise Refused("4a", f"У рецепті призначено лише {recipe.prescribed_quantity} уп.")
            batch = self._batch_for(pharmacist, recipe, quantity, today)
            stock_before = batch.quantity
            self.verifier.redeem(recipe, quantity, today)

            sale = Sale(f"Ч-{self.uow.next_number('sale')}", now, PaymentMethod(payment), pharmacist,
                        prescription=recipe, pricing=recipe.pricing_policy())
            sale.add_line(batch, quantity)
            sale.complete()
            self.uow.batches.save(batch)
            self.uow.sales.save(sale)

            ensure(recipe.state is PrescriptionState.REDEEMED, "рецепт погашено")
            ensure(batch.quantity == stock_before - quantity, "залишок партії зменшено")
        return SaleResult(sale.number, batch.drug.trade_name, batch.series, quantity, sale.total)

    def _valid_recipe(self, number: str, today: date) -> EPrescription:
        try:
            return self.verifier.verify(number, today)
        except Refused as refusal:
            if refusal.flow == "2a":
                raise Refused("6a", f"{refusal}. Продаж не оформлено.") from None
            raise

    def _batch_for(self, pharmacist, recipe: EPrescription, quantity: int, today: date) -> Batch:
        here = pharmacist.pharmacy
        batch = here.pick_batch_for_sale(recipe.inn, quantity, today)
        if batch is None:
            others = self.uow.pharmacies.chain().pharmacies_with(recipe.inn, quantity, today, excluding=here)
            hint = f" Препарат є в аптеках: {', '.join(p.number for p in others)}." if others else ""
            raise Refused("5a", f"В аптеці немає придатної партії.{hint}")
        return batch
