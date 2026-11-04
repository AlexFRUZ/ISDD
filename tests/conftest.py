"""Спільні фікстури тестів контролерів."""
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from pharmacy.controllers.prescription_sale_controller import PrescriptionSaleController
from pharmacy.controllers.reservation_controller import ReservationController
from pharmacy.network.registry import LocalRegistry
from pharmacy.persistence.seed import build_demo_store
from pharmacy.persistence.store import MemoryStore

TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 10, 0)


@dataclass
class Context:
    store: MemoryStore
    registry: LocalRegistry
    reservations: ReservationController
    sales: PrescriptionSaleController

    def batch(self, series):
        return next(b for p in self.store.chain().pharmacies for b in p.batches if b.series == series)


@pytest.fixture
def ctx():
    store = build_demo_store(TODAY)
    registry = LocalRegistry(store.prescriptions)

    def clock():
        return NOW

    return Context(store, registry, ReservationController(store, registry, clock),
                   PrescriptionSaleController(store, registry, clock))
