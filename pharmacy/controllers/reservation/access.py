from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pharmacy.domain import Reservation
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


@dataclass(frozen=True)
class ReservationStatus:
    code: str
    state: str
    expires_at: datetime
    notified: bool


def status_of(reservation: Reservation) -> ReservationStatus:
    return ReservationStatus(reservation.code, reservation.state.value, reservation.expires_at,
                             reservation.customer_notified)


def reservation_at_pharmacy(uow: UnitOfWork, personnel_number: str, code: str) -> Reservation:
    pharmacist = uow.pharmacists.get(personnel_number)
    if pharmacist is None:
        raise Refused("пм", f"Фармацевта {personnel_number} не знайдено")
    reservation = uow.reservations.get(code)
    if reservation is None:
        raise Refused("3a", f"Резервування {code} не знайдено")
    if not reservation.is_at_pharmacy(pharmacist.pharmacy.number):
        raise Refused("3b", f"Резервування {code} належить іншій аптеці")
    return reservation
