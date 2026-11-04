"""Тести машини станів класу Reservation: кожен рядок transitions.csv (ЛР 4)."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import domain as d
from fsm_check import PSEUDO_STATE, load_transitions

HERE = Path(__file__).parent
ROWS = load_transitions(HERE / "transitions.csv")
NOW = datetime(2026, 11, 4, 10, 0)
BEFORE_EXPIRY = NOW + timedelta(hours=1)
AFTER_EXPIRY = NOW + timedelta(hours=25)
STOCK = 5


def make_reservation(state: str, stock: int = STOCK) -> d.Reservation:
    """Резервування в заданому стані з узгодженим залишком партії."""
    pharmacy = d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    drug = d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    batch = d.Batch("S-1", date(2027, 11, 4), Decimal("1"), Decimal("2"), stock, drug, pharmacy)
    customer = d.Customer("+380671112233", "Іваненко Марія")
    reservation = d.Reservation("R-1", NOW, 2, customer, batch)
    reservation.state = d.ReservationState(state)
    if state in ("Підтверджене", "Готове", "Продовжене"):
        batch.reserved = reservation.quantity
    return reservation


def test_every_csv_state_exists_in_code():
    assert {r.state for r in ROWS} | {r.next for r in ROWS} <= {s.value for s in d.ReservationState}


def test_new_object_starts_in_initial_state():
    initial = next(r.next for r in ROWS if r.state == PSEUDO_STATE)
    reservation = make_reservation(initial)
    fresh = d.Reservation("R-2", NOW, 1, reservation.customer, reservation.batch)
    assert fresh.state.value == initial


@pytest.mark.parametrize(
    "row", [r for r in ROWS if r.state != PSEUDO_STATE],
    ids=lambda r: f"{r.state}-{r.event}-{r.guard or 'без умови'}",
)
def test_every_transition(row):
    stock = 1 if row.guard == "немає залишку" else STOCK
    reservation = make_reservation(row.state, stock)
    moment = AFTER_EXPIRY if row.guard == "строк дії минув" else BEFORE_EXPIRY
    reservation.fire(row.event, moment)
    assert reservation.state.value == row.next


@pytest.mark.parametrize("state, event", [
    ("Нове", "видати"),
    ("Нове", "зібрати"),
    ("Підтверджене", "продовжити"),
    ("Продовжене", "продовжити"),
    ("Видане", "скасувати"),
    ("Скасоване", "підтвердити"),
    ("Прострочене", "видати"),
])
def test_invalid_state_event_pairs(state, event):
    reservation = make_reservation(state)
    with pytest.raises(d.TransitionError, match="недопустима"):
        reservation.fire(event, BEFORE_EXPIRY)
    assert reservation.state.value == state  # недопустима подія не змінює стан


def test_issue_after_expiry_is_refused_by_guard():
    reservation = make_reservation("Готове")
    with pytest.raises(d.TransitionError, match="не виконано умову"):
        reservation.issue(AFTER_EXPIRY)


def test_expire_before_deadline_is_refused_by_guard():
    reservation = make_reservation("Готове")
    with pytest.raises(d.TransitionError, match="не виконано умову"):
        reservation.expire(BEFORE_EXPIRY)


def test_action_confirm_blocks_stock():
    reservation = make_reservation("Нове")
    reservation.confirm()
    assert reservation.batch.available == STOCK - 2


def test_action_cancel_returns_stock():
    reservation = make_reservation("Підтверджене")
    reservation.cancel()
    assert reservation.batch.available == STOCK and reservation.batch.quantity == STOCK


def test_action_expire_returns_stock():
    reservation = make_reservation("Готове")
    reservation.expire(AFTER_EXPIRY)
    assert reservation.batch.available == STOCK


def test_action_issue_writes_off_stock():
    reservation = make_reservation("Готове")
    reservation.issue(BEFORE_EXPIRY)
    assert reservation.batch.quantity == STOCK - 2 and reservation.batch.reserved == 0


def test_action_prepare_notifies_customer():
    reservation = make_reservation("Підтверджене")
    reservation.prepare()
    assert reservation.customer_notified


def test_action_extend_adds_24_hours():
    reservation = make_reservation("Готове")
    deadline = reservation.expires_at
    reservation.extend()
    assert reservation.expires_at == deadline + timedelta(hours=24) and reservation.extensions == 1


def test_finished_reservations_are_not_active():
    for state in ("Видане", "Скасоване", "Прострочене"):
        assert not make_reservation(state).is_active


def test_unknown_guard_in_table_is_an_error(tmp_path):
    table = tmp_path / "t.csv"
    table.write_text("state;event;guard;action;next\nНове;підтвердити;магія;;Готове\n", encoding="utf-8")
    with pytest.raises(d.DomainError, match="невідомі умова"):
        d.load_transitions(table)
