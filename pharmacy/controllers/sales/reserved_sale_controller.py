from __future__ import annotations

from pharmacy.controllers.reservation.interface import ReservationProvider
from pharmacy.controllers.sales.common import SaleResult, pharmacist_with
from pharmacy.controllers.sales.verification import PrescriptionVerificationService
from pharmacy.domain import PaymentMethod, PrescriptionState, ReservationState, Sale
from pharmacy.foundation.clock import Clock, system_clock
from pharmacy.foundation.contracts import ensure
from pharmacy.foundation.errors import Refused
from pharmacy.persistence.repositories import UnitOfWork


class ReservedSaleController:
    def __init__(self, uow: UnitOfWork, reservations: ReservationProvider,
                 verifier: PrescriptionVerificationService, clock: Clock = system_clock) -> None:
        self.uow = uow
        self.reservations = reservations
        self.verifier = verifier
        self.clock = clock

    def issue(self, pharmacist_number: str, code: str, payment: str = "картка") -> SaleResult:
        now = self.clock()
        with self.uow.transaction():
            pharmacist = pharmacist_with(self.uow, pharmacist_number)
            reservation = self.reservations.find(code)
            if reservation is None:
                raise Refused("3a", f"Резервування {code} не знайдено")
            if not reservation.is_at_pharmacy(pharmacist.pharmacy.number):
                raise Refused("3b", f"Резервування {code} належить іншій аптеці")
            if reservation.state not in {ReservationState.READY, ReservationState.EXTENDED}:
                raise Refused("4a", f"Резервування {code} не готове до видачі: "
                                    f"стан «{reservation.state.value}»")
            if reservation.is_overdue(now):
                raise Refused("4b", f"Строк дії резервування {code} минув")

            recipe = reservation.prescription
            if recipe is not None:
                verified = self.verifier.verified_for(recipe.number, reservation.batch.drug.inn, now.date())
                if not verified.allows_quantity(reservation.quantity):
                    raise Refused("5a", f"У рецепті призначено лише {verified.prescribed_quantity} уп.")
                self.verifier.redeem(verified, reservation.quantity, now.date())

            if recipe is None:
                sale = Sale(f"Ч-{self.uow.next_number('sale')}", now, PaymentMethod(payment), pharmacist,
                            customer=reservation.customer)
            else:
                sale = Sale(f"Ч-{self.uow.next_number('sale')}", now, PaymentMethod(payment), pharmacist,
                            customer=reservation.customer, prescription=recipe,
                            pricing=recipe.pricing_policy())
            self.reservations.complete_issue(reservation, now)
            sale.add_reserved_line(reservation)
            sale.complete()
            self.uow.sales.save(sale)

            ensure(reservation.state is ReservationState.ISSUED, "резервування видано")
            if recipe is not None:
                ensure(recipe.state is PrescriptionState.REDEEMED, "рецепт погашено")
        batch = reservation.batch
        return SaleResult(sale.number, batch.drug.trade_name, batch.series, reservation.quantity, sale.total)
