import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from pharmacy.controllers.prescription_sale_controller import PrescriptionSaleController
from pharmacy.controllers.reservation_controller import ReservationController
from pharmacy.network.registry import LocalRegistry
from pharmacy.persistence.memory import MemoryUnitOfWork
from pharmacy.persistence.seed import populate
from pharmacy.persistence.sqlite import SqliteUnitOfWork, create_schema

TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 10, 0)


def make_memory_uow():
    return MemoryUnitOfWork()


def make_sqlite_uow():
    connection = sqlite3.connect(":memory:")
    create_schema(connection)
    return SqliteUnitOfWork(connection)


BACKENDS = {"memory": make_memory_uow, "sqlite": make_sqlite_uow}


@dataclass
class Context:
    uow: object
    registry: LocalRegistry
    reservations: ReservationController
    sales: PrescriptionSaleController

    def batch(self, series):
        pharmacy, drug = {"AM": ("А-01", "Амоксил"), "IN": ("А-02", "Актрапід"),
                          "PA": ("А-01", "Парацетамол")}[series[:2]]
        self.uow.clear()
        return self.uow.batches.get((pharmacy, drug, series))

    def recipe(self, number):
        self.uow.clear()
        return self.uow.prescriptions.get(number)


def build_context(uow):
    populate(uow, TODAY)
    registry = LocalRegistry(uow.prescriptions)

    def clock():
        return NOW

    return Context(uow, registry, ReservationController(uow, registry, clock),
                   PrescriptionSaleController(uow, registry, clock))


@pytest.fixture(params=BACKENDS, ids=str)
def uow(request):
    unit = BACKENDS[request.param]()
    yield unit
    unit.close()


@pytest.fixture
def ctx(uow):
    return build_context(uow)


@pytest.fixture
def sqlite_ctx():
    unit = make_sqlite_uow()
    yield build_context(unit)
    unit.close()
