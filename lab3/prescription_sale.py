from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lab2"))

from domain import (
    Batch, EPrescription, PaymentMethod, Pharmacist, Pharmacy, PharmacyChain,
    PrescriptionState, Sale,
)


class SaleRefused(Exception):
    def __init__(self, flow: str, message: str) -> None:
        super().__init__(message)
        self.flow = flow


class RegistryUnavailable(Exception):
    pass


class InMemoryRegistry:
    def __init__(self, prescriptions: list[EPrescription]) -> None:
        self._prescriptions = {p.number: p for p in prescriptions}
        self.online = True

    def find(self, number: str) -> EPrescription | None:
        return self._prescriptions.get(number)

    def redeem(self, recipe: EPrescription, quantity: int, today) -> None:
        if not self.online:
            raise RegistryUnavailable
        recipe.redeem(quantity, today)


class PrescriptionSaleService:
    def __init__(self, chain: PharmacyChain, registry: InMemoryRegistry, pharmacist: Pharmacist) -> None:
        self.chain = chain
        self.registry = registry
        self.pharmacist = pharmacist
        self._next_number = 1

    def sell(self, recipe_number: str, quantity: int, now: datetime,
             payment: PaymentMethod = PaymentMethod.CARD) -> Sale:
        today = now.date()
        recipe = self._check_recipe(recipe_number, today)
        self._check_quantity(recipe, quantity)
        batch = self._pick_batch(recipe, quantity, today)
        self._redeem(recipe, quantity, today)
        return self._create_sale(recipe, batch, quantity, now, payment)

    def _check_recipe(self, number: str, today) -> EPrescription:
        recipe = self.registry.find(number)
        if recipe is None:
            raise SaleRefused("3a", f"Рецепт {number} не знайдено в реєстрі")
        if not recipe.is_valid(today):
            raise SaleRefused("3b", f"Рецепт {number} недійсний: {self._invalid_reason(recipe)}")
        return recipe

    @staticmethod
    def _invalid_reason(recipe: EPrescription) -> str:
        if recipe.state is PrescriptionState.ACTIVE:
            return "минув строк дії"
        return f"стан «{recipe.state.value}»"

    @staticmethod
    def _check_quantity(recipe: EPrescription, quantity: int) -> None:
        if quantity > recipe.prescribed_quantity:
            raise SaleRefused("4a", f"У рецепті призначено лише {recipe.prescribed_quantity} уп.")

    def _pick_batch(self, recipe: EPrescription, quantity: int, today) -> Batch:
        here = self._suitable_batches(self.pharmacist.pharmacy, recipe.inn, quantity, today)
        if here:
            return min(here, key=lambda b: b.expiry_date)
        others = [p.number for p in self.chain.pharmacies if p is not self.pharmacist.pharmacy
                  and self._suitable_batches(p, recipe.inn, quantity, today)]
        hint = f" Препарат є в аптеках: {', '.join(others)}." if others else ""
        raise SaleRefused("5a", f"В аптеці немає придатної партії.{hint}")

    @staticmethod
    def _suitable_batches(pharmacy: Pharmacy, inn: str, quantity: int, today) -> list[Batch]:
        return [b for b in pharmacy.batches
                if b.drug.inn == inn and not b.is_expired(today) and b.available >= quantity]

    def _redeem(self, recipe: EPrescription, quantity: int, today) -> None:
        try:
            self.registry.redeem(recipe, quantity, today)
        except RegistryUnavailable:
            raise SaleRefused("6a", "Реєстр е-рецептів недоступний. Продаж не оформлено.") from None

    def _create_sale(self, recipe: EPrescription, batch: Batch, quantity: int,
                     now: datetime, payment: PaymentMethod) -> Sale:
        sale = Sale(f"Ч-{self._next_number}", now, payment, self.pharmacist, prescription=recipe)
        self._next_number += 1
        sale.add_line(batch, quantity)
        sale.total = (sale.total * (Decimal("1") - recipe.reimbursement_share)).quantize(Decimal("0.01"))
        sale.complete()
        return sale
