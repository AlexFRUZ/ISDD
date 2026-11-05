from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

CENT = Decimal("0.01")


class PricingPolicy(Protocol):
    def amount_due(self, subtotal: Decimal) -> Decimal: ...


@dataclass(frozen=True)
class StandardPricing:
    def amount_due(self, subtotal: Decimal) -> Decimal:
        return subtotal.quantize(CENT)


@dataclass(frozen=True)
class ReimbursedPricing:
    share: Decimal

    def amount_due(self, subtotal: Decimal) -> Decimal:
        return (subtotal * (Decimal("1") - self.share)).quantize(CENT)


@dataclass(frozen=True)
class LoyaltyPricing:
    percent: Decimal

    def amount_due(self, subtotal: Decimal) -> Decimal:
        return (subtotal * (Decimal("100") - self.percent) / Decimal("100")).quantize(CENT)
