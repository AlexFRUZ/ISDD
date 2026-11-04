"""Резервування з табличною машиною станів (таблицю перевіряє lab4/fsm_check.py)."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from pharmacy.domain.batch import MIN_SHELF_LIFE_DAYS
from pharmacy.foundation.contracts import invariant, keeps_invariant, require
from pharmacy.foundation.errors import DomainError, TransitionError

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch
    from pharmacy.domain.customer import Customer
    from pharmacy.domain.prescription import EPrescription

MAX_ACTIVE_RESERVATIONS = 3
MIN_RESERVATION_QUANTITY = 1
MAX_RESERVATION_QUANTITY = 6
RESERVATION_HOURS = 24
MAX_EXTENSIONS = 1
TRANSITIONS_FILE = Path(__file__).with_name("transitions.csv")


class ReservationState(Enum):
    NEW = "Нове"
    CONFIRMED = "Підтверджене"
    READY = "Готове"
    EXTENDED = "Продовжене"
    ISSUED = "Видане"
    CANCELLED = "Скасоване"
    EXPIRED = "Прострочене"
    ARCHIVED = "[*]"


ACTIVE_RESERVATION_STATES = {
    ReservationState.NEW, ReservationState.CONFIRMED,
    ReservationState.READY, ReservationState.EXTENDED,
}


@dataclass(eq=False)
class Reservation:
    code: str
    created_at: datetime
    quantity: int
    customer: Customer
    batch: Batch
    prescription: EPrescription | None = None
    expires_at: datetime | None = None
    extensions: int = 0
    state: ReservationState = ReservationState.NEW
    customer_notified: bool = False

    def __post_init__(self) -> None:
        require(self.is_allowed_quantity(self.quantity),
                f"Кількість має бути від {MIN_RESERVATION_QUANTITY} до {MAX_RESERVATION_QUANTITY} упаковок")
        require(self.customer.can_reserve, f"Покупець уже має {MAX_ACTIVE_RESERVATIONS} активні резервування")
        today = self.created_at.date()
        if self.batch.drug.requires_prescription:
            require(self._prescription_matches(today), "Для рецептурного препарату потрібен чинний е-рецепт")
        require(self.batch.has_shelf_life_for_reservation(today),
                f"Залишковий строк партії менший за {MIN_SHELF_LIFE_DAYS} днів")
        self.expires_at = self.expires_at or self.created_at + timedelta(hours=RESERVATION_HOURS)
        self.customer.reservations.append(self)
        self.check_invariant()

    @classmethod
    def restore(cls, **fields) -> Reservation:
        """Відновлює збережений об'єкт без умов створення.

        Умови створення діють лише в момент резервування. Давнє резервування не стає
        некоректним через те, що партія з часом втратила залишковий строк придатності.
        """
        reservation = cls.__new__(cls)
        reservation.__dict__.update(fields)
        reservation.customer.reservations.append(reservation)
        return reservation

    def check_invariant(self) -> None:
        invariant(self.is_allowed_quantity(self.quantity), "Кількість резервування поза допустимими межами")
        invariant(self.expires_at > self.created_at, "Строк дії має бути пізнішим за дату створення")
        invariant(self.extensions <= MAX_EXTENSIONS, "Резервування можна продовжити лише один раз")

    @staticmethod
    def is_allowed_quantity(quantity: int) -> bool:
        return MIN_RESERVATION_QUANTITY <= quantity <= MAX_RESERVATION_QUANTITY

    def _prescription_matches(self, today: date) -> bool:
        return self.prescription is not None and self.prescription.matches(self.batch.drug.inn, today)

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_RESERVATION_STATES

    @keeps_invariant
    def fire(self, event: str, moment: datetime | None = None) -> None:
        """Обробляє подію за таблицею переходів; недопустима подія кидає виняток."""
        moment = moment or self.created_at
        transitions = TRANSITIONS.get((self.state.value, event))
        if not transitions:
            raise TransitionError(f"Подія «{event}» недопустима у стані «{self.state.value}»")
        for transition in transitions:
            if GUARDS[transition.guard](self, moment):
                ACTIONS[transition.action](self, moment)
                self.state = ReservationState(transition.next)
                return
        raise TransitionError(f"Подія «{event}»: не виконано умову переходу зі стану «{self.state.value}»")

    def confirm(self) -> None:
        self.fire("підтвердити")

    def prepare(self) -> None:
        self.fire("зібрати")

    def issue(self, moment: datetime) -> None:
        self.fire("видати", moment)

    def extend(self) -> None:
        self.fire("продовжити")

    def cancel(self) -> None:
        self.fire("скасувати")

    def expire(self, moment: datetime) -> None:
        self.fire("настав строк", moment)

    def archive(self) -> None:
        self.fire("архівувати")

    def _block_stock(self, _moment: datetime) -> None:
        self.batch.block(self.quantity)

    def _release_stock(self, _moment: datetime) -> None:
        self.batch.unblock(self.quantity)

    def _write_off_stock(self, moment: datetime) -> None:
        self.batch.unblock(self.quantity)
        self.batch.write_off_sold(self.quantity, moment.date())

    def _notify_customer(self, _moment: datetime) -> None:
        self.customer_notified = True

    def _add_extension(self, _moment: datetime) -> None:
        self.extensions += 1
        self.expires_at += timedelta(hours=RESERVATION_HOURS)


GUARDS = {
    "": lambda r, moment: True,
    "є залишок": lambda r, moment: r.batch.available >= r.quantity,
    "немає залишку": lambda r, moment: r.batch.available < r.quantity,
    "строк дії минув": lambda r, moment: moment > r.expires_at,
    "строк дії не минув": lambda r, moment: moment <= r.expires_at,
}
ACTIONS = {
    "": lambda r, moment: None,
    "заблокувати залишок": Reservation._block_stock,
    "повернути залишок": Reservation._release_stock,
    "списати залишок": Reservation._write_off_stock,
    "сповістити покупця": Reservation._notify_customer,
    "додати 24 години": Reservation._add_extension,
}


@dataclass(frozen=True)
class Transition:
    guard: str
    action: str
    next: str


def load_transitions(path: Path = TRANSITIONS_FILE) -> dict[tuple[str, str], list[Transition]]:
    """Завантажує таблицю переходів. Невідома умова чи дія є помилкою моделі."""
    table: dict[tuple[str, str], list[Transition]] = defaultdict(list)
    with open(path, encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            if row["guard"] not in GUARDS or row["action"] not in ACTIONS:
                raise DomainError(f"Таблиця переходів: невідомі умова чи дія в рядку {row}")
            table[(row["state"], row["event"])].append(Transition(row["guard"], row["action"], row["next"]))
    return dict(table)


TRANSITIONS = load_transitions()
