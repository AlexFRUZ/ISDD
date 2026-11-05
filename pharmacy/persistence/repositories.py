from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Protocol, TypeVar

from pharmacy.domain import (
    Batch, Customer, Delivery, Director, Drug, EPrescription, Manager, Pharmacist, Pharmacy,
    PharmacyChain, PrescriptionState, Reservation, Sale, Supplier, WriteOff,
)

Entity = TypeVar("Entity")
Key = TypeVar("Key")
BatchKey = tuple[str, str, str]


class Repository(Protocol[Entity, Key]):
    def get(self, key: Key) -> Entity | None: ...
    def save(self, entity: Entity) -> None: ...
    def delete(self, key: Key) -> None: ...


class PharmacyRepository(Repository[Pharmacy, str], Protocol):
    def chain(self) -> PharmacyChain: ...
    def save_chain(self, chain: PharmacyChain) -> None: ...
    def find_by_city(self, city: str) -> list[Pharmacy]: ...


class PharmacistRepository(Repository[Pharmacist, str], Protocol):
    def find_by_pharmacy(self, pharmacy_number: str) -> list[Pharmacist]: ...


class DrugRepository(Repository[Drug, str], Protocol):
    def find_by_inn(self, inn: str) -> list[Drug]: ...


class BatchRepository(Repository[Batch, BatchKey], Protocol):
    def find_expiring(self, until: date) -> list[Batch]: ...
    def expiry_of_series(self, trade_name: str, series: str) -> date | None: ...


class ManagerRepository(Repository[Manager, str], Protocol):
    pass


class DirectorRepository(Repository[Director, str], Protocol):
    pass


class SupplierRepository(Repository[Supplier, str], Protocol):
    pass


class DeliveryRepository(Repository[Delivery, str], Protocol):
    pass


class WriteOffRepository(Repository[WriteOff, str], Protocol):
    def find_by_pharmacy(self, pharmacy_number: str) -> list[WriteOff]: ...


class CustomerRepository(Repository[Customer, str], Protocol):
    pass


class ReservationRepository(Repository[Reservation, str], Protocol):
    def find_active_by_customer(self, phone: str) -> list[Reservation]: ...
    def find_overdue(self, moment: datetime) -> list[Reservation]: ...


class PrescriptionRepository(Repository[EPrescription, str], Protocol):
    def find_by_state(self, state: PrescriptionState) -> list[EPrescription]: ...


class SaleRepository(Repository[Sale, str], Protocol):
    def find_by_period(self, start: datetime, end: datetime) -> list[Sale]: ...


class UnitOfWork(Protocol):
    pharmacies: PharmacyRepository
    pharmacists: PharmacistRepository
    drugs: DrugRepository
    batches: BatchRepository
    customers: CustomerRepository
    reservations: ReservationRepository
    prescriptions: PrescriptionRepository
    sales: SaleRepository
    managers: ManagerRepository
    directors: DirectorRepository
    suppliers: SupplierRepository
    deliveries: DeliveryRepository
    write_offs: WriteOffRepository

    def transaction(self) -> AbstractContextManager[None]: ...
    def next_number(self, kind: str) -> int: ...
    def clear(self) -> None: ...
    def close(self) -> None: ...
