from __future__ import annotations

from pharmacy.controllers.reservation.access import ReservationStatus, reservation_at_pharmacy, status_of
from pharmacy.domain import Reservation, ReservationState
from pharmacy.foundation.contracts import ensure
from pharmacy.foundation.errors import Refused
from pharmacy.network.sms import SmsGateway, SmsUnavailable
from pharmacy.persistence.repositories import UnitOfWork


class PrepareReservationController:
    def __init__(self, uow: UnitOfWork, sms: SmsGateway) -> None:
        self.uow = uow
        self.sms = sms

    def prepare(self, personnel_number: str, code: str) -> ReservationStatus:
        with self.uow.transaction():
            reservation = reservation_at_pharmacy(self.uow, personnel_number, code)
            if reservation.state is not ReservationState.CONFIRMED:
                raise Refused("4a", f"Резервування {code} не очікує збирання: стан «{reservation.state.value}»")
            reservation.prepare()
            self._notify(reservation)
            self.uow.reservations.save(reservation)
            ensure(reservation.state is ReservationState.READY, "резервування готове до видачі")
            return status_of(reservation)

    def _notify(self, reservation: Reservation) -> None:
        text = f"Резервування {reservation.code} готове. Заберіть до {reservation.expires_at:%d.%m.%Y %H:%M}"
        try:
            self.sms.send(reservation.customer.phone, text)
        except SmsUnavailable:
            reservation.customer_notified = False
