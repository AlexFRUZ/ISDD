from __future__ import annotations

from datetime import date

from pharmacy.controllers.warehouse.common import DeliveryLine
from pharmacy.domain import Drug, Pharmacy
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


class DeliveryValidator:

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def validated_drugs(self, pharmacy: Pharmacy, lines: list[DeliveryLine], today: date) -> dict[str, Drug]:
        drugs: dict[str, Drug] = {}
        seen: set[tuple[str, str]] = set()
        for line in lines:
            drugs[line.trade_name] = self._known_drug(line)
            self._check_expiry(line, today)
            self._check_series_is_new(pharmacy, line, seen)
            self._check_series_expiry(line)
        return drugs

    def _known_drug(self, line: DeliveryLine) -> Drug:
        drug = self.uow.drugs.get(line.trade_name)
        if drug is None:
            raise Refused("4a", f"Препарат {line.trade_name} відсутній у каталозі")
        return drug

    @staticmethod
    def _check_expiry(line: DeliveryLine, today: date) -> None:
        if line.expiry_date <= today:
            raise Refused("4b", f"Серія {line.series}: строк придатності вже минув")

    def _check_series_is_new(self, pharmacy: Pharmacy, line: DeliveryLine, seen: set[tuple[str, str]]) -> None:
        key = (line.trade_name, line.series)
        if key in seen or self.uow.batches.get((pharmacy.number, *key)) is not None:
            raise Refused("5a", f"Серія {line.series} препарату {line.trade_name} уже є в аптеці")
        seen.add(key)

    def _check_series_expiry(self, line: DeliveryLine) -> None:
        known = self.uow.batches.expiry_of_series(line.trade_name, line.series)
        if known is not None and known != line.expiry_date:
            raise Refused("5b", f"Серія {line.series} має інший строк придатності: {known}")
