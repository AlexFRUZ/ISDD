"""Інтерфейси репозиторіїв (ЛР 7, завдання 2).

Контролери залежать лише від цих протоколів. Реалізації лежать у memory.py і sqlite.py.
Репозиторій є для кожного кореневого об'єкта, який використовують контролери: лікар
зберігається разом із рецептом, позиції разом із продажем, а мережа разом з аптеками.
Постачальник і поставка мають таблиці в схемі, але варіанти використання UC10-UC13 ще не
реалізовано, тому репозиторіїв для них немає.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Protocol, TypeVar

from pharmacy.domain import (
    Batch, Customer, Drug, EPrescription, Pharmacist, Pharmacy, PharmacyChain,
    PrescriptionState, Reservation, Sale,
)

Entity = TypeVar("Entity")
Key = TypeVar("Key")
BatchKey = tuple[str, str, str]  # номер аптеки, торгова назва, серія


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


class CustomerRepository(Repository[Customer, str], Protocol):
    pass


class ReservationRepository(Repository[Reservation, str], Protocol):
    def find_active_by_customer(self, phone: str) -> list[Reservation]: ...


class PrescriptionRepository(Repository[EPrescription, str], Protocol):
    def find_by_state(self, state: PrescriptionState) -> list[EPrescription]: ...


class SaleRepository(Repository[Sale, str], Protocol):
    def find_by_period(self, start: datetime, end: datetime) -> list[Sale]: ...


class UnitOfWork(Protocol):
    """Набір репозиторіїв, які змінюються в одній транзакції."""

    pharmacies: PharmacyRepository
    pharmacists: PharmacistRepository
    drugs: DrugRepository
    batches: BatchRepository
    customers: CustomerRepository
    reservations: ReservationRepository
    prescriptions: PrescriptionRepository
    sales: SaleRepository

    def transaction(self) -> AbstractContextManager[None]: ...
    def next_number(self, kind: str) -> int: ...
    def clear(self) -> None: ...
    def close(self) -> None: ...
