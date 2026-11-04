"""Доменна модель ІС «Мережа аптек» (ЛР 2, завдання 3).

Кожен клас моделі є класом Python, атрибути є полями, наслідування є успадкуванням,
асоціації є посиланнями або колекціями, а асоціативний клас «Позиція продажу» має
посилання на обидва кінці зв'язку. Кратності й інваріанти перевіряють методи класів.
Поточну дату передають явно, щоб правила можна було тестувати детерміновано.

ЛР 4: клас Reservation отримав табличну машину станів. Таблицю завантажено з того
самого файлу transitions.csv, який перевіряє fsm_check.py, тому модель і код не
розходяться. Обмеження «продовжити один раз» виражено самою таблицею: зі стану
«Продовжене» подію «продовжити» не визначено.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path

MAX_ACTIVE_RESERVATIONS = 3
MIN_RESERVATION_QUANTITY = 1
MAX_RESERVATION_QUANTITY = 5
RESERVATION_HOURS = 24
PRESCRIPTION_VALID_DAYS = 30
MIN_SHELF_LIFE_DAYS = 30
TRANSITIONS_FILE = Path(__file__).resolve().parent.parent / "lab4" / "transitions.csv"


class DomainError(Exception):
    """Порушення кратності або інваріанта предметної області."""


class TransitionError(DomainError):
    """Подія недопустима в поточному стані або не виконано умову переходу."""


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


class PrescriptionState(Enum):
    ACTIVE = "активний"
    REDEEMED = "погашений"
    CANCELLED = "скасований"


class PaymentMethod(Enum):
    CASH = "готівка"
    CARD = "картка"


# eq=False: об'єкти предметної області порівнюють за ідентичністю, а не за полями.
@dataclass(eq=False)
class Pharmacy:
    number: str
    address: str
    city: str
    phone: str
    schedule: str
    batches: list[Batch] = field(default_factory=list, repr=False)
    pharmacists: list[Pharmacist] = field(default_factory=list, repr=False)


@dataclass(eq=False)
class PharmacyChain:
    name: str
    edrpou: str
    pharmacies: list[Pharmacy]

    def __post_init__(self) -> None:
        if not self.pharmacies:
            raise DomainError("Мережа має складатися щонайменше з однієї аптеки")

    def remove_pharmacy(self, pharmacy: Pharmacy) -> None:
        if len(self.pharmacies) == 1:
            raise DomainError("Не можна видалити останню аптеку мережі")
        self.pharmacies.remove(pharmacy)


@dataclass(eq=False)
class Pharmacist:
    personnel_number: str
    full_name: str
    pharmacy: Pharmacy

    def __post_init__(self) -> None:
        self.pharmacy.pharmacists.append(self)


@dataclass(eq=False)
class Drug:
    trade_name: str
    inn: str
    dosage_form: str
    dosage: str
    manufacturer: str
    batches: list[Batch] = field(default_factory=list, repr=False)

    @property
    def requires_prescription(self) -> bool:
        return False


@dataclass(eq=False)
class PrescriptionDrug(Drug):
    control_group: str = "загальна"

    @property
    def requires_prescription(self) -> bool:
        return True


@dataclass(eq=False)
class OtcDrug(Drug):
    check_limit: int = 10


@dataclass(eq=False)
class Batch:
    series: str
    expiry_date: date
    purchase_price: Decimal
    retail_price: Decimal
    quantity: int
    drug: Drug
    pharmacy: Pharmacy
    reserved: int = 0

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise DomainError("Кількість у партії не може бути від'ємною")
        if not 0 <= self.reserved <= self.quantity:
            raise DomainError("Зарезервована кількість має бути в межах кількості партії")
        self.drug.batches.append(self)
        self.pharmacy.batches.append(self)

    @property
    def available(self) -> int:
        return self.quantity - self.reserved

    def is_expired(self, today: date) -> bool:
        return self.expiry_date <= today

    def has_shelf_life_for_reservation(self, today: date) -> bool:
        return self.expiry_date - today >= timedelta(days=MIN_SHELF_LIFE_DAYS)

    def block(self, quantity: int) -> None:
        """Блокує кількість під резервування, не змінюючи фізичний залишок."""
        if quantity > self.available:
            raise DomainError(f"Партія {self.series}: доступно лише {self.available} уп.")
        self.reserved += quantity

    def unblock(self, quantity: int) -> None:
        if quantity > self.reserved:
            raise DomainError(f"Партія {self.series}: заблоковано лише {self.reserved} уп.")
        self.reserved -= quantity

    def write_off_sold(self, quantity: int, today: date) -> None:
        """Зменшує фізичний залишок під час продажу."""
        if self.is_expired(today):
            raise DomainError(f"Партія {self.series}: строк придатності минув")
        if quantity > self.available:
            raise DomainError(f"Партія {self.series}: доступно лише {self.available} уп.")
        self.quantity -= quantity


@dataclass(eq=False)
class Supplier:
    name: str
    phone: str
    deliveries: list[Delivery] = field(default_factory=list, repr=False)


@dataclass(eq=False)
class Delivery:
    invoice_number: str
    delivery_date: date
    supplier: Supplier
    batches: list[Batch]

    def __post_init__(self) -> None:
        if not self.batches:
            raise DomainError("Поставка має містити щонайменше одну партію")
        self.supplier.deliveries.append(self)


@dataclass(eq=False)
class Doctor:
    full_name: str
    specialty: str
    prescriptions: list[EPrescription] = field(default_factory=list, repr=False)


@dataclass(eq=False)
class EPrescription:
    number: str
    issued_on: date
    inn: str
    prescribed_quantity: int
    doctor: Doctor
    reimbursement_share: Decimal = Decimal("0")
    state: PrescriptionState = PrescriptionState.ACTIVE

    def __post_init__(self) -> None:
        if self.prescribed_quantity < 1:
            raise DomainError("Призначена кількість має бути додатною")
        if not Decimal("0") <= self.reimbursement_share <= Decimal("1"):
            raise DomainError("Частка реімбурсації має бути в межах від 0 до 1")
        self.doctor.prescriptions.append(self)

    def is_valid(self, today: date) -> bool:
        age = today - self.issued_on
        return self.state is PrescriptionState.ACTIVE and age <= timedelta(days=PRESCRIPTION_VALID_DAYS)

    def redeem(self, quantity: int, today: date) -> None:
        if not self.is_valid(today):
            raise DomainError(f"Рецепт {self.number} недійсний")
        if quantity > self.prescribed_quantity:
            raise DomainError(f"Рецепт {self.number}: призначено лише {self.prescribed_quantity} уп.")
        self.state = PrescriptionState.REDEEMED


@dataclass(eq=False)
class Customer:
    phone: str
    full_name: str
    reservations: list[Reservation] = field(default_factory=list, repr=False)

    @property
    def active_reservations(self) -> list[Reservation]:
        return [r for r in self.reservations if r.is_active]


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
        if not MIN_RESERVATION_QUANTITY <= self.quantity <= MAX_RESERVATION_QUANTITY:
            raise DomainError(
                f"Кількість має бути від {MIN_RESERVATION_QUANTITY} до {MAX_RESERVATION_QUANTITY} упаковок"
            )
        if len(self.customer.active_reservations) >= MAX_ACTIVE_RESERVATIONS:
            raise DomainError(f"Покупець уже має {MAX_ACTIVE_RESERVATIONS} активні резервування")
        today = self.created_at.date()
        if self.batch.drug.requires_prescription and not self._prescription_matches(today):
            raise DomainError("Для рецептурного препарату потрібен чинний е-рецепт")
        if not self.batch.has_shelf_life_for_reservation(today):
            raise DomainError(f"Залишковий строк партії менший за {MIN_SHELF_LIFE_DAYS} днів")
        self.expires_at = self.expires_at or self.created_at + timedelta(hours=RESERVATION_HOURS)
        self.customer.reservations.append(self)

    def _prescription_matches(self, today: date) -> bool:
        recipe = self.prescription
        return recipe is not None and recipe.is_valid(today) and recipe.inn == self.batch.drug.inn

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_RESERVATION_STATES

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


@dataclass(eq=False)
class Sale:
    number: str
    sold_at: datetime
    payment_method: PaymentMethod
    pharmacist: Pharmacist
    customer: Customer | None = None
    prescription: EPrescription | None = None
    total: Decimal = Decimal("0")
    lines: list[SaleLine] = field(default_factory=list, repr=False)

    def add_line(self, batch: Batch, quantity: int) -> SaleLine:
        if any(line.batch is batch for line in self.lines):
            raise DomainError(f"Партія {batch.series} вже є в чеку {self.number}")
        today = self.sold_at.date()
        if batch.drug.requires_prescription and self.prescription is None:
            raise DomainError("Рецептурний препарат продається лише за е-рецептом")
        batch.write_off_sold(quantity, today)
        line = SaleLine(quantity, batch.retail_price, self, batch)
        self.lines.append(line)
        self.total += line.amount
        return line

    def complete(self) -> None:
        if not self.lines:
            raise DomainError("Чек має містити щонайменше одну позицію")


@dataclass(eq=False)
class SaleLine:
    """Асоціативний клас зв'язку «Продаж – Партія»."""

    quantity: int
    unit_price: Decimal
    sale: Sale
    batch: Batch

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise DomainError("Кількість у позиції має бути додатною")

    @property
    def amount(self) -> Decimal:
        return self.unit_price * self.quantity
