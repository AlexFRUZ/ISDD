from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pharmacy.foundation.contracts import require

if TYPE_CHECKING:
    from pharmacy.domain.chain import Pharmacy
    from pharmacy.domain.sale import Sale


@dataclass(frozen=True)
class PharmacySalesRow:
    pharmacy_number: str
    city: str
    sales_count: int
    packs: int
    revenue: Decimal

    @property
    def average_check(self) -> Decimal:
        if self.sales_count == 0:
            return Decimal("0.00")
        return (self.revenue / self.sales_count).quantize(Decimal("0.01"))


@dataclass
class SalesReport:

    start: date
    end: date
    rows: list[PharmacySalesRow] = field(default_factory=list)

    @classmethod
    def build(cls, start: date, end: date, pharmacies: list[Pharmacy], sales: list[Sale]) -> SalesReport:
        require(start <= end, "Початок періоду не може бути пізніше за його кінець")
        rows = []
        for pharmacy in sorted(pharmacies, key=lambda p: p.number):
            own = [s for s in sales if s.pharmacy.number == pharmacy.number]
            rows.append(PharmacySalesRow(
                pharmacy.number, pharmacy.city, len(own), sum(s.packs for s in own),
                sum((s.total for s in own), Decimal("0.00"))))
        return cls(start, end, rows)

    @property
    def sales_count(self) -> int:
        return sum(r.sales_count for r in self.rows)

    @property
    def packs(self) -> int:
        return sum(r.packs for r in self.rows)

    @property
    def revenue(self) -> Decimal:
        return sum((r.revenue for r in self.rows), Decimal("0.00"))
