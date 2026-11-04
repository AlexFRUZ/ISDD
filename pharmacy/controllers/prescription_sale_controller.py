"""Контролер UC7 «Продати за е-рецептом».

Контролер лише координує кроки варіанта використання: правила застосовують доменні
класи (ЛР 6, шаблон Expert), а створення позицій виконує сам продаж (шаблон Creator).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pharmacy.domain import Batch, EPrescription, PaymentMethod, Pharmacist, PrescriptionState, Sale
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure, require
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
        """Контракт: lab6/contracts.md, метод 1."""
        require(quantity >= 1, "Кількість має бути додатною")
        now = self.clock()
        today = now.date()
        pharmacist = self._pharmacist(pharmacist_number)
        recipe = self._valid_recipe(recipe_number, today)
        if not recipe.allows_quantity(quantity):
            raise Refused("4a", f"У рецепті призначено лише {recipe.prescribed_quantity} уп.")
        batch = self._batch_for(pharmacist, recipe, quantity, today)
        stock_before = batch.quantity
        self._redeem(recipe, quantity, today)

        sale = Sale(f"Ч-{self.store.next_number('sale')}", now, PaymentMethod(payment), pharmacist,
                    prescription=recipe, pricing=recipe.pricing_policy())
        sale.add_line(batch, quantity)
        sale.complete()
        self.store.save_sale(sale)
        self.store.commit()

        ensure(recipe.state is PrescriptionState.REDEEMED, "рецепт погашено")
        ensure(batch.quantity == stock_before - quantity, "залишок партії зменшено")
        return SaleResult(sale.number, batch.drug.trade_name, batch.series, quantity, sale.total)

    def _pharmacist(self, number: str) -> Pharmacist:
        pharmacist = self.store.find_pharmacist(number)
        if pharmacist is None:
            raise Refused("пм", f"Фармацевта {number} не знайдено")
        return pharmacist

    def _valid_recipe(self, number: str, today: date) -> EPrescription:
        recipe = self.registry.find(number)
        if recipe is None:
            raise Refused("3a", f"Рецепт {number} не знайдено в реєстрі")
        reason = recipe.invalid_reason(today)
        if reason:
            raise Refused("3b", f"Рецепт {number} недійсний: {reason}")
        return recipe

    def _batch_for(self, pharmacist: Pharmacist, recipe: EPrescription, quantity: int, today: date) -> Batch:
        here = pharmacist.pharmacy
        batch = here.pick_batch_for_sale(recipe.inn, quantity, today)
        if batch is None:
            others = self.store.chain().pharmacies_with(recipe.inn, quantity, today, excluding=here)
            hint = f" Препарат є в аптеках: {', '.join(p.number for p in others)}." if others else ""
            raise Refused("5a", f"В аптеці немає придатної партії.{hint}")
        return batch

    def _redeem(self, recipe: EPrescription, quantity: int, today: date) -> None:
        try:
            self.registry.redeem(recipe, quantity, today)
        except RegistryUnavailable:
            raise Refused("6a", "Реєстр е-рецептів недоступний. Продаж не оформлено.") from None
