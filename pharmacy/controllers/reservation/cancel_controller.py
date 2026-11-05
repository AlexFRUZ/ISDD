from __future__ import annotations

from pharmacy.controllers.reservation.access import ReservationStatus, status_of
from pharmacy.domain import ReservationState
from pharmacy.foundation.contracts import ensure
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


class CancelReservationController:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def cancel(self, phone: str, code: str) -> ReservationStatus:
        with self.uow.transaction():
            reservation = self.uow.reservations.get(code)
            if reservation is None or not reservation.belongs_to(phone):
                raise Refused("3a", f"Резервування {code} не знайдено серед резервувань покупця")
            if not reservation.is_active:
                raise Refused("3b", f"Резервування {code} уже не активне: стан «{reservation.state.value}»")
            available_before = reservation.batch.available
            reservation.cancel()
            self.uow.batches.save(reservation.batch)
            self.uow.reservations.save(reservation)
            ensure(reservation.state is ReservationState.CANCELLED, "резервування скасовано")
            ensure(reservation.batch.available == available_before + reservation.quantity, "залишок повернуто")
            return status_of(reservation)
