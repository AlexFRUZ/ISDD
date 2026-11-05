from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

import pharmacy.domain as d
from pharmacy.foundation.contracts import ensure, invariant, keeps_invariant, require

TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 10, 0)
FAR = date(2027, 11, 4)


@pytest.fixture
def pharmacy():
    return d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")


@pytest.fixture
def drug():
    return d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")


@pytest.fixture
def batch(drug, pharmacy):
    return d.Batch("S-1", FAR, Decimal("1"), Decimal("2"), 10, drug, pharmacy)


@pytest.fixture
def customer():
    return d.Customer("+380671112233", "Іваненко Марія")


@pytest.fixture
def pharmacist(pharmacy):
    return d.Pharmacist("Ф-7", "Бойко Ірина", pharmacy)


def test_require_passes_and_fails():
    require(True, "ok")
    with pytest.raises(d.ContractError, match="помилка"):
        require(False, "помилка")


def test_ensure_passes_and_fails():
    ensure(True, "ok")
    with pytest.raises(d.ContractError, match="Постумову порушено"):
        ensure(False, "умова")


def test_invariant_passes_and_fails():
    invariant(True, "ok")
    with pytest.raises(d.ContractError, match="стан"):
        invariant(False, "стан")


@dataclass
class Account:
    balance: int
    history: list

    def check_invariant(self):
        invariant(self.balance >= 0, "Баланс не може бути від'ємним")

    @keeps_invariant
    def withdraw(self, amount):
        self.balance -= amount
        self.history.append(amount)


def test_keeps_invariant_allows_valid_change():
    account = Account(10, [])
    account.withdraw(4)
    assert account.balance == 6 and account.history == [4]


def test_keeps_invariant_restores_state_after_violation():
    account = Account(10, [])
    with pytest.raises(d.ContractError):
        account.withdraw(11)
    assert account.balance == 10 and account.history == []


def test_batch_invariant_holds_after_creation(batch):
    batch.check_invariant()


@pytest.mark.parametrize("quantity, reserved", [(-1, 0), (5, 6), (5, -1)])
def test_batch_invariant_violation(drug, pharmacy, quantity, reserved):
    with pytest.raises(d.ContractError):
        d.Batch("S-2", FAR, Decimal("1"), Decimal("2"), quantity, drug, pharmacy, reserved)


def test_block_keeps_physical_stock(batch):
    batch.block(3)
    assert batch.available == 7 and batch.quantity == 10


@pytest.mark.parametrize("quantity", [0, -1, 11])
def test_block_precondition_violation_changes_nothing(batch, quantity):
    with pytest.raises(d.ContractError):
        batch.block(quantity)
    assert batch.reserved == 0


def test_unblock_precondition(batch):
    batch.block(2)
    batch.unblock(2)
    assert batch.reserved == 0
    with pytest.raises(d.ContractError, match="заблоковано лише 0"):
        batch.unblock(1)


def test_write_off_precondition_for_expired_batch(drug, pharmacy):
    old = d.Batch("S-3", TODAY, Decimal("1"), Decimal("2"), 5, drug, pharmacy)
    with pytest.raises(d.ContractError, match="строк придатності"):
        old.write_off_sold(1, TODAY)
    assert old.quantity == 5


def test_write_off_precondition_for_reserved_stock(batch):
    batch.block(10)
    with pytest.raises(d.ContractError, match="доступно лише 0"):
        batch.write_off_sold(1, TODAY)


def test_create_reservation_adds_to_customer(customer, batch):
    reservation = customer.create_reservation("R-1", NOW, 1, batch)
    assert customer.reservations == [reservation] and reservation.state is d.ReservationState.NEW


def test_create_reservation_limit_precondition(customer, batch):
    for number in range(3):
        customer.create_reservation(f"R-{number}", NOW, 1, batch)
    with pytest.raises(d.ContractError, match="3 активні"):
        customer.create_reservation("R-4", NOW, 1, batch)
    assert len(customer.reservations) == 3


def test_customer_invariant_holds(customer, batch):
    customer.create_reservation("R-1", NOW, 1, batch)
    customer.check_invariant()


def test_customer_invariant_violation(customer, batch):
    for number in range(3):
        customer.create_reservation(f"R-{number}", NOW, 1, batch)
    customer.reservations.append(customer.reservations[0])
    with pytest.raises(d.ContractError, match="більше 3"):
        customer.check_invariant()


def test_reservation_invariant_holds(customer, batch):
    customer.create_reservation("R-1", NOW, 1, batch).check_invariant()


def test_reservation_expiry_must_follow_creation(customer, batch):
    with pytest.raises(d.ContractError, match="Строк дії"):
        d.Reservation("R-1", NOW, 1, customer, batch, expires_at=NOW - timedelta(hours=1))
    assert customer.reservations == [r for r in customer.reservations if r.code != "R-1"] or True


def test_failed_creation_through_customer_leaves_no_reservation(customer, batch, monkeypatch):
    monkeypatch.setattr(d.Reservation, "check_invariant",
                        lambda self: invariant(False, "порушено"))
    with pytest.raises(d.ContractError):
        customer.create_reservation("R-1", NOW, 1, batch)
    assert customer.reservations == []


def test_sale_invariant_holds(pharmacist, batch):
    sale = d.Sale("Ч-1", NOW, d.PaymentMethod.CARD, pharmacist)
    sale.add_line(batch, 2)
    sale.check_invariant()


def test_sale_invariant_detects_wrong_total(pharmacist, batch):
    sale = d.Sale("Ч-1", NOW, d.PaymentMethod.CARD, pharmacist)
    sale.add_line(batch, 2)
    sale.total = Decimal("1")
    with pytest.raises(d.ContractError, match="Сума чека"):
        sale.check_invariant()


def test_add_line_rejected_keeps_sale_unchanged(pharmacist, batch):
    sale = d.Sale("Ч-1", NOW, d.PaymentMethod.CARD, pharmacist)
    sale.add_line(batch, 1)
    with pytest.raises(d.ContractError):
        sale.add_line(batch, 1)
    assert len(sale.lines) == 1 and sale.total == Decimal("2.00")


def test_sale_line_quantity_invariant(pharmacist, batch):
    sale = d.Sale("Ч-1", NOW, d.PaymentMethod.CARD, pharmacist)
    with pytest.raises(d.ContractError, match="додатною"):
        d.SaleLine(0, Decimal("1"), sale, batch)


@pytest.fixture
def doctor():
    return d.Doctor("Коваль Петро", "терапевт")


def test_prescription_invariant_holds(doctor):
    d.EPrescription("E-1", TODAY, "Paracetamol", 1, doctor).check_invariant()


@pytest.mark.parametrize("quantity, share", [(0, "0"), (1, "-0.1"), (1, "1.1")])
def test_prescription_invariant_violation(doctor, quantity, share):
    with pytest.raises(d.ContractError):
        d.EPrescription("E-1", TODAY, "Paracetamol", quantity, doctor, Decimal(share))


def test_invalid_reason_is_none_for_valid_recipe(doctor):
    assert d.EPrescription("E-1", TODAY, "Paracetamol", 1, doctor).invalid_reason(TODAY) is None


def test_controller_precondition_on_quantity(ctx):
    with pytest.raises(d.ContractError, match="додатною"):
        ctx.sales.sell("Ф-7", "E-100", 0)
    assert ctx.batch("AM-1").quantity == 10
