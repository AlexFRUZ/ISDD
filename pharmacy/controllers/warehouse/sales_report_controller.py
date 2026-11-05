from __future__ import annotations

from datetime import date, datetime, time

from pharmacy.controllers.warehouse.common import reader_with
from pharmacy.domain import Manager, SalesReport
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


class SalesReportController:

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def report(self, user_number: str, start: date, end: date,
               pharmacy_number: str | None = None) -> SalesReport:
        with self.uow.transaction():
            user = reader_with(self.uow, user_number)
            if start > end:
                raise Refused("3a", "Початок періоду не може бути пізніше за його кінець")
            pharmacies = self._scope(user, pharmacy_number)
            sales = self.uow.sales.find_by_period(datetime.combine(start, time.min),
                                                  datetime.combine(end, time.max))
            numbers = {p.number for p in pharmacies}
            return SalesReport.build(start, end, pharmacies, [s for s in sales if s.pharmacy.number in numbers])

    def _scope(self, user, pharmacy_number: str | None) -> list:
        if pharmacy_number is not None:
            pharmacy = self.uow.pharmacies.get(pharmacy_number)
            if pharmacy is None:
                raise Refused("4a", f"Аптеку {pharmacy_number} не знайдено")
            if not user.may_view(pharmacy):
                raise Refused("4b", "Завідувач бачить продажі лише своєї аптеки")
            return [pharmacy]
        if isinstance(user, Manager):
            return [user.pharmacy]
        return self.uow.pharmacies.chain().pharmacies
