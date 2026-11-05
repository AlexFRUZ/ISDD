from __future__ import annotations

from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.persistence.repositories import UnitOfWork


class ExpireReservationsController:
    def __init__(self, uow: UnitOfWork, clock: Clock = system_clock) -> None:
        self.uow = uow
        self.clock = clock

    def expire_overdue(self) -> list[str]:
        now = self.clock()
        with self.uow.transaction():
            overdue = self.uow.reservations.find_overdue(now)
            for reservation in overdue:
                reservation.expire(now)
                self.uow.batches.save(reservation.batch)
                self.uow.reservations.save(reservation)
            return [reservation.code for reservation in overdue]
