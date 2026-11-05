from __future__ import annotations

import pickle
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime

from pharmacy.domain import (
    Batch, Drug, EPrescription, Pharmacist, Pharmacy, PharmacyChain,
    PrescriptionState, Reservation, Sale, WriteOff,
)


@dataclass
class MemoryData:
    chain: PharmacyChain | None = None
    pharmacies: dict = field(default_factory=dict)
    pharmacists: dict = field(default_factory=dict)
    drugs: dict = field(default_factory=dict)
    batches: dict = field(default_factory=dict)
    customers: dict = field(default_factory=dict)
    reservations: dict = field(default_factory=dict)
    prescriptions: dict = field(default_factory=dict)
    sales: dict = field(default_factory=dict)
    managers: dict = field(default_factory=dict)
    directors: dict = field(default_factory=dict)
    suppliers: dict = field(default_factory=dict)
    deliveries: dict = field(default_factory=dict)
    write_offs: dict = field(default_factory=dict)
    counters: dict = field(default_factory=lambda: defaultdict(int))


class MemoryRepository:
    def __init__(self, uow: MemoryUnitOfWork, table: str, key: Callable) -> None:
        self._uow = uow
        self._table = table
        self._key = key

    @property
    def _items(self) -> dict:
        return getattr(self._uow.data, self._table)

    def get(self, key):
        return self._items.get(key)

    def save(self, entity) -> None:
        self._items[self._key(entity)] = entity

    def delete(self, key) -> None:
        self._items.pop(key, None)


class MemoryPharmacyRepository(MemoryRepository):
    def chain(self) -> PharmacyChain:
        return self._uow.data.chain

    def save_chain(self, chain: PharmacyChain) -> None:
        self._uow.data.chain = chain
        for pharmacy in chain.pharmacies:
            self.save(pharmacy)

    def find_by_city(self, city: str) -> list[Pharmacy]:
        return [p for p in self._items.values() if p.city == city]


class MemoryPharmacistRepository(MemoryRepository):
    def find_by_pharmacy(self, pharmacy_number: str) -> list[Pharmacist]:
        return [p for p in self._items.values() if p.pharmacy.number == pharmacy_number]


class MemoryDrugRepository(MemoryRepository):
    def find_by_inn(self, inn: str) -> list[Drug]:
        return [d for d in self._items.values() if d.inn == inn]


class MemoryBatchRepository(MemoryRepository):
    def find_expiring(self, until: date) -> list[Batch]:
        return sorted((b for b in self._items.values() if b.expiry_date <= until),
                      key=lambda b: b.expiry_date)

    def expiry_of_series(self, trade_name: str, series: str) -> date | None:
        return next((b.expiry_date for b in self._items.values()
                     if b.drug.trade_name == trade_name and b.series == series), None)


class MemoryDeliveryRepository(MemoryRepository):
    def save(self, delivery) -> None:
        self._uow.suppliers.save(delivery.supplier)
        for batch in delivery.batches:
            self._uow.batches.save(batch)
        super().save(delivery)


class MemoryWriteOffRepository(MemoryRepository):
    def find_by_pharmacy(self, pharmacy_number: str) -> list[WriteOff]:
        return sorted((w for w in self._items.values() if w.batch.pharmacy.number == pharmacy_number),
                      key=lambda w: w.number)


class MemoryReservationRepository(MemoryRepository):
    def find_active_by_customer(self, phone: str) -> list[Reservation]:
        return [r for r in self._items.values() if r.customer.phone == phone and r.is_active]

    def find_overdue(self, moment: datetime) -> list[Reservation]:
        return [r for r in self._items.values() if r.is_overdue(moment)]


class MemoryPrescriptionRepository(MemoryRepository):
    def find_by_state(self, state: PrescriptionState) -> list[EPrescription]:
        return [p for p in self._items.values() if p.state is state]


class MemorySaleRepository(MemoryRepository):
    def find_by_period(self, start: datetime, end: datetime) -> list[Sale]:
        return [s for s in self._items.values() if start <= s.sold_at <= end]


def _batch_key(batch: Batch) -> tuple[str, str, str]:
    return batch.pharmacy.number, batch.drug.trade_name, batch.series


class MemoryUnitOfWork:
    def __init__(self) -> None:
        self.data = MemoryData()
        self.pharmacies = MemoryPharmacyRepository(self, "pharmacies", lambda p: p.number)
        self.pharmacists = MemoryPharmacistRepository(self, "pharmacists", lambda p: p.personnel_number)
        self.drugs = MemoryDrugRepository(self, "drugs", lambda d: d.trade_name)
        self.batches = MemoryBatchRepository(self, "batches", _batch_key)
        self.customers = MemoryRepository(self, "customers", lambda c: c.phone)
        self.reservations = MemoryReservationRepository(self, "reservations", lambda r: r.code)
        self.prescriptions = MemoryPrescriptionRepository(self, "prescriptions", lambda p: p.number)
        self.sales = MemorySaleRepository(self, "sales", lambda s: s.number)
        self.managers = MemoryRepository(self, "managers", lambda m: m.personnel_number)
        self.directors = MemoryRepository(self, "directors", lambda d: d.personnel_number)
        self.suppliers = MemoryRepository(self, "suppliers", lambda s: s.name)
        self.deliveries = MemoryDeliveryRepository(self, "deliveries", lambda d: d.invoice_number)
        self.write_offs = MemoryWriteOffRepository(self, "write_offs", lambda w: w.number)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        snapshot = pickle.dumps(self.data)
        try:
            yield
        except BaseException:
            self.data = pickle.loads(snapshot)
            raise

    def next_number(self, kind: str) -> int:
        self.data.counters[kind] += 1
        return self.data.counters[kind]

    def clear(self) -> None:
        pass

    def close(self) -> None:
        pass
