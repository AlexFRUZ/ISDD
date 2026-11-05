from __future__ import annotations

from datetime import timedelta

from pharmacy.controllers.reservation.access import ReservationStatus, reservation_at_pharmacy, status_of
from pharmacy.domain import RESERVATION_HOURS, ReservationState
from pharmacy.foundation.contracts import ensure
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


class ExtendReservationController:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def extend(self, personnel_number: str, code: str) -> ReservationStatus:
        with self.uow.transaction():
            reservation = reservation_at_pharmacy(self.uow, personnel_number, code)
            if reservation.state is ReservationState.EXTENDED:
                raise Refused("4a", f"Резервування {code} вже продовжено один раз")
            if reservation.state is not ReservationState.READY:
                raise Refused("4b", f"Продовжити можна лише готове резервування: стан «{reservation.state.value}»")
            deadline = reservation.expires_at
            reservation.extend()
            self.uow.reservations.save(reservation)
            ensure(reservation.expires_at == deadline + timedelta(hours=RESERVATION_HOURS), "строк дії продовжено")
            return status_of(reservation)
