import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from pharmacy.controllers.prescription_sale_controller import PrescriptionSaleController
from pharmacy.controllers.reservation.cancel_controller import CancelReservationController
from pharmacy.controllers.reservation.expire_controller import ExpireReservationsController
from pharmacy.controllers.reservation.extend_controller import ExtendReservationController
from pharmacy.controllers.reservation.interface import ReservationProvider
from pharmacy.controllers.reservation.prepare_controller import PrepareReservationController
from pharmacy.controllers.reservation.reserve_controller import ReservationController
from pharmacy.controllers.sales import OtcSaleController, PrescriptionVerificationService, ReservedSaleController
from pharmacy.controllers.warehouse import (
    ExpiryController, ReceiveDeliveryController, SalesReportController, WriteOffController,
)
from pharmacy.network.registry import LocalRegistry
from pharmacy.network.sms import LocalSmsGateway
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
    cancellation: CancelReservationController
    preparation: PrepareReservationController
    extension: ExtendReservationController
    expiration: ExpireReservationsController
    sms: LocalSmsGateway
    provider: ReservationProvider
    reserved_sales: ReservedSaleController
    otc_sales: OtcSaleController
    recipe_verification: PrescriptionVerificationService
    clock: dict
    deliveries: ReceiveDeliveryController
    write_offs: WriteOffController
    expiry: ExpiryController
    sales_reports: SalesReportController

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

    moment = {"now": NOW}

    def clock():
        return moment["now"]

    sms = LocalSmsGateway()
    verification = PrescriptionVerificationService(registry)
    provider = ReservationProvider(uow)
    return Context(uow, registry, ReservationController(uow, verification, clock),
                   PrescriptionSaleController(uow, verification, clock), CancelReservationController(uow),
                   PrepareReservationController(uow, sms), ExtendReservationController(uow),
                   ExpireReservationsController(uow, clock), sms, provider,
                   ReservedSaleController(uow, provider, verification, clock),
                   OtcSaleController(uow, clock), verification, moment,
                   ReceiveDeliveryController(uow, clock), WriteOffController(uow, clock),
                   ExpiryController(uow, clock), SalesReportController(uow))


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
