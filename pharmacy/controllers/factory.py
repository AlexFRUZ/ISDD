from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pharmacy.controllers.prescription_sale_controller import PrescriptionSaleController
from pharmacy.controllers.reservation.cancel_controller import CancelReservationController
from pharmacy.controllers.reservation.expire_controller import ExpireReservationsController
from pharmacy.controllers.reservation.extend_controller import ExtendReservationController
from pharmacy.controllers.reservation.interface import RegistryRecipeVerifier
from pharmacy.controllers.reservation.prepare_controller import PrepareReservationController
from pharmacy.controllers.reservation.reserve_controller import ReservationController
from pharmacy.network.registry import LocalRegistry
from pharmacy.network.sms import LocalSmsGateway
from pharmacy.persistence.repositories import UnitOfWork
from pharmacy.persistence.sqlite import create_database, open_database


@dataclass
class App:
    uow: UnitOfWork
    reservations: ReservationController
    cancellation: CancelReservationController
    preparation: PrepareReservationController
    extension: ExtendReservationController
    expiration: ExpireReservationsController
    sales: PrescriptionSaleController

    def close(self) -> None:
        self.uow.close()


def create_demo_data(path: str | Path) -> None:
    create_database(path)


def build_app(path: str | Path, registry_online: bool = True, sms_online: bool = True) -> App:
    uow = open_database(path)
    registry = LocalRegistry(uow.prescriptions, registry_online)
    return App(
        uow,
        ReservationController(uow, RegistryRecipeVerifier(registry)),
        CancelReservationController(uow),
        PrepareReservationController(uow, LocalSmsGateway(sms_online)),
        ExtendReservationController(uow),
        ExpireReservationsController(uow),
        PrescriptionSaleController(uow, registry),
    )
