"""Спільний інтерфейс сховища та його реалізація в пам'яті (ЛР 5).

Контролери залежать лише від протоколу Store. Тому в ЛР 7 реалізацію можна замінити
на SQLite, не змінюючи контролерів.
"""
from __future__ import annotations

import pickle
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from pharmacy.domain import Customer, EPrescription, Pharmacist, Pharmacy, PharmacyChain, Reservation, Sale


class Store(Protocol):
    prescriptions: dict[str, EPrescription]

    def chain(self) -> PharmacyChain: ...
    def find_pharmacy(self, number: str) -> Pharmacy | None: ...
    def find_pharmacist(self, personnel_number: str) -> Pharmacist | None: ...
    def find_customer(self, phone: str) -> Customer | None: ...
    def save_customer(self, customer: Customer) -> None: ...
    def save_reservation(self, reservation: Reservation) -> None: ...
    def find_reservation(self, code: str) -> Reservation | None: ...
    def save_sale(self, sale: Sale) -> None: ...
    def next_number(self, kind: str) -> int: ...
    def commit(self) -> None: ...


class MemoryStore:
    """Словник у пам'яті. Шлях до файлу потрібен, щоб стан зберігався між запусками CLI."""

    def __init__(self, chain: PharmacyChain, path: str | Path | None = None) -> None:
        self._chain = chain
        self.path = Path(path) if path else None
        self.customers: dict[str, Customer] = {}
        self.pharmacists: dict[str, Pharmacist] = {}
        self.prescriptions: dict[str, EPrescription] = {}
        self.reservations: dict[str, Reservation] = {}
        self.sales: dict[str, Sale] = {}
        self.counters: dict[str, int] = defaultdict(int)

    @classmethod
    def load(cls, path: str | Path) -> MemoryStore:
        with open(path, "rb") as stream:
            store = pickle.load(stream)
        store.path = Path(path)
        return store

    def chain(self) -> PharmacyChain:
        return self._chain

    def find_pharmacy(self, number: str) -> Pharmacy | None:
        return next((p for p in self._chain.pharmacies if p.number == number), None)

    def find_pharmacist(self, personnel_number: str) -> Pharmacist | None:
        return self.pharmacists.get(personnel_number)

    def find_customer(self, phone: str) -> Customer | None:
        return self.customers.get(phone)

    def save_customer(self, customer: Customer) -> None:
        self.customers[customer.phone] = customer

    def save_reservation(self, reservation: Reservation) -> None:
        self.reservations[reservation.code] = reservation

    def find_reservation(self, code: str) -> Reservation | None:
        return self.reservations.get(code)

    def save_sale(self, sale: Sale) -> None:
        self.sales[sale.number] = sale

    def next_number(self, kind: str) -> int:
        self.counters[kind] += 1
        return self.counters[kind]

    def commit(self) -> None:
        if self.path is not None:
            with open(self.path, "wb") as stream:
                pickle.dump(self, stream)
