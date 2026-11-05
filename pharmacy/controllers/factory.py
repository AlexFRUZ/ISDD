from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pharmacy.controllers.prescription_sale_controller import PrescriptionSaleController
from pharmacy.controllers.reservation_controller import ReservationController
from pharmacy.network.registry import LocalRegistry
from pharmacy.persistence.repositories import UnitOfWork
from pharmacy.persistence.sqlite import create_database, open_database


@dataclass
class App:
    uow: UnitOfWork
    reservations: ReservationController
    sales: PrescriptionSaleController

    def close(self) -> None:
        self.uow.close()


def create_demo_data(path: str | Path) -> None:
    create_database(path)


def build_app(path: str | Path, registry_online: bool = True) -> App:
    uow = open_database(path)
    registry = LocalRegistry(uow.prescriptions, registry_online)
    return App(uow, ReservationController(uow, registry), PrescriptionSaleController(uow, registry))
