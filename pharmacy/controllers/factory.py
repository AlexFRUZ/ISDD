"""Збірка застосунку. Завдяки цьому модулю рівень подання не залежить від рівня збереження."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pharmacy.controllers.prescription_sale_controller import PrescriptionSaleController
from pharmacy.controllers.reservation_controller import ReservationController
from pharmacy.network.registry import LocalRegistry
from pharmacy.persistence.seed import build_demo_store
from pharmacy.persistence.store import MemoryStore


@dataclass
class App:
    reservations: ReservationController
    sales: PrescriptionSaleController


def create_demo_data(path: str | Path, today: date) -> None:
    build_demo_store(today, path).commit()


def build_app(path: str | Path, registry_online: bool = True) -> App:
    store = MemoryStore.load(path)
    registry = LocalRegistry(store.prescriptions, registry_online)
    return App(ReservationController(store, registry), PrescriptionSaleController(store, registry))
