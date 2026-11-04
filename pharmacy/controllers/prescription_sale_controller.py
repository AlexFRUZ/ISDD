"""Контролер UC7 «Продати за е-рецептом» (ЛР 5)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pharmacy.domain import Batch, EPrescription, PaymentMethod, Pharmacy, PrescriptionState, Sale
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.errors import Refused
from pharmacy.network.registry import PrescriptionRegistry, RegistryUnavailable
from pharmacy.persistence.store import Store


@dataclass(frozen=True)
class SaleResult:
    number: str
    trade_name: str
    series: str
    quantity: int
    total: Decimal


class PrescriptionSaleController:
    def __init__(self, store: Store, registry: PrescriptionRegistry, clock: Clock = system_clock) -> None:
        self.store = store
        self.registry = registry
        self.clock = clock

    def sell(self, pharmacist_number: str, recipe_number: str, quantity: int,
             payment: str = "картка") -> SaleResult:
        now = self.clock()
        today = now.date()
        pharmacist = self.store.find_pharmacist(pharmacist_number)
        if pharmacist is None:
            raise Refused("пм", f"Фармацевта {pharmacist_number} не знайдено")
        recipe = self._check_recipe(recipe_number, today)
        if quantity > recipe.prescribed_quantity:
            raise Refused("4a", f"У рецепті призначено лише {recipe.prescribed_quantity} уп.")
        batch = self._pick_batch(pharmacist.pharmacy, recipe.inn, quantity, today)
        try:
            self.registry.redeem(recipe, quantity, today)
        except RegistryUnavailable:
            raise Refused("6a", "Реєстр е-рецептів недоступний. Продаж не оформлено.") from None
        sale = self._create_sale(pharmacist, recipe, batch, quantity, now, PaymentMethod(payment))
        self.store.save_sale(sale)
        self.store.commit()
        return SaleResult(sale.number, batch.drug.trade_name, batch.series, quantity, sale.total)

    def _check_recipe(self, number: str, today: date) -> EPrescription:
        recipe = self.registry.find(number)
        if recipe is None:
            raise Refused("3a", f"Рецепт {number} не знайдено в реєстрі")
        if not recipe.is_valid(today):
            if recipe.state is PrescriptionState.ACTIVE:
                reason = "минув строк дії"
            else:
                reason = f"стан «{recipe.state.value}»"
            raise Refused("3b", f"Рецепт {number} недійсний: {reason}")
        return recipe

    def _pick_batch(self, pharmacy: Pharmacy, inn: str, quantity: int, today: date) -> Batch:
        here = self._suitable(pharmacy, inn, quantity, today)
        if here:
            return min(here, key=lambda b: b.expiry_date)
        others = [p.number for p in self.store.chain().pharmacies
                  if p is not pharmacy and self._suitable(p, inn, quantity, today)]
        hint = f" Препарат є в аптеках: {', '.join(others)}." if others else ""
        raise Refused("5a", f"В аптеці немає придатної партії.{hint}")

    @staticmethod
    def _suitable(pharmacy: Pharmacy, inn: str, quantity: int, today: date) -> list[Batch]:
        return [b for b in pharmacy.batches
                if b.drug.inn == inn and not b.is_expired(today) and b.available >= quantity]

    def _create_sale(self, pharmacist, recipe: EPrescription, batch: Batch, quantity: int,
                     now: datetime, payment: PaymentMethod) -> Sale:
        number = f"Ч-{self.store.next_number('sale')}"
        sale = Sale(number, now, payment, pharmacist, prescription=recipe)
        sale.add_line(batch, quantity)
        sale.total = (sale.total * (Decimal("1") - recipe.reimbursement_share)).quantize(Decimal("0.01"))
        sale.complete()
        return sale
