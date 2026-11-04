"""Ціноутворення: шаблон Strategy (ЛР 6, завдання 3).

Продаж не знає, як саме обчислюється сума до сплати. Новий спосіб ціноутворення
додається новим класом, а класи Sale і контролери при цьому не змінюються.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

CENT = Decimal("0.01")


class PricingPolicy(Protocol):
    def amount_due(self, subtotal: Decimal) -> Decimal: ...


@dataclass(frozen=True)
class StandardPricing:
    """Покупець сплачує повну суму чека."""

    def amount_due(self, subtotal: Decimal) -> Decimal:
        return subtotal.quantize(CENT)


@dataclass(frozen=True)
class ReimbursedPricing:
    """Частину вартості за рецептом відшкодовує програма реімбурсації."""

    share: Decimal

    def amount_due(self, subtotal: Decimal) -> Decimal:
        return (subtotal * (Decimal("1") - self.share)).quantize(CENT)


@dataclass(frozen=True)
class LoyaltyPricing:
    """Знижка за картою лояльності, у відсотках."""

    percent: Decimal

    def amount_due(self, subtotal: Decimal) -> Decimal:
        return (subtotal * (Decimal("100") - self.percent) / Decimal("100")).quantize(CENT)
