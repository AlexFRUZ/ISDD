"""Класи еквівалентності й граничні значення бізнес-правил (ЛР 7, завдання 3).

Таблиці тестових випадків наведено в lab7/equivalence_classes.md.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

import pharmacy.domain as d
from conftest import NOW, TODAY
from pharmacy.foundation.errors import Refused

PHONE = "+380671112233"


def reserve(ctx, quantity=1, drug="Парацетамол"):
    return ctx.reservations.reserve(PHONE, "А-01", drug, quantity)


# --- Правило 1: кількість упаковок у резервуванні (R2.2) ---------------------------

@pytest.mark.req("R2.2")
@pytest.mark.parametrize("quantity", [1, 2, 5, 6])
def test_quantity_in_allowed_class(ctx, quantity):
    assert reserve(ctx, quantity).quantity == quantity


@pytest.mark.req("R2.2")
@pytest.mark.parametrize("quantity", [-1, 0, 7, 8])
def test_quantity_outside_allowed_class(ctx, quantity):
    with pytest.raises(Refused, match="від 1 до 6") as refusal:
        reserve(ctx, quantity)
    assert refusal.value.flow == "4a"


# --- Правило 2: кількість активних резервувань покупця (R2.1) ----------------------

@pytest.mark.req("R2.1")
@pytest.mark.parametrize("already_active", [0, 1, 2])
def test_active_count_allows_new_reservation(ctx, already_active):
    for _ in range(already_active):
        reserve(ctx)
    assert reserve(ctx).code


@pytest.mark.req("R2.1")
@pytest.mark.parametrize("already_active", [3])
def test_active_count_blocks_new_reservation(ctx, already_active):
    for _ in range(already_active):
        reserve(ctx)
    with pytest.raises(Refused, match="3 активні"):
        reserve(ctx)


# --- Правило 3: строк дії рецепта (R6.2) -------------------------------------------

@pytest.fixture
def doctor():
    return d.Doctor("Коваль Петро", "терапевт")


@pytest.mark.req("R6.2")
@pytest.mark.parametrize("age_days, valid", [(0, True), (1, True), (29, True), (30, True), (31, False), (365, False)])
def test_prescription_age(doctor, age_days, valid):
    recipe = d.EPrescription("E-1", TODAY - timedelta(days=age_days), "X", 1, doctor)
    assert recipe.is_valid(TODAY) is valid


@pytest.mark.req("R6.2")
def test_prescription_issued_in_future_is_invalid(doctor):
    recipe = d.EPrescription("E-1", TODAY + timedelta(days=1), "X", 1, doctor)
    assert recipe.invalid_reason(TODAY) == "дата виписки ще не настала"


# --- Правило 4: залишковий строк придатності для резервування (R2.5) ----------------

@pytest.mark.req("R2.5")
@pytest.mark.parametrize("days_left, can_reserve", [(0, False), (29, False), (30, True), (31, True)])
def test_shelf_life_for_reservation(days_left, can_reserve):
    pharmacy = d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    drug = d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    batch = d.Batch("S-1", TODAY + timedelta(days=days_left), Decimal("1"), Decimal("2"), 5, drug, pharmacy)
    assert batch.can_be_reserved(1, TODAY) is can_reserve


# --- Правило 5: строк придатності під час продажу (R8) -----------------------------

@pytest.mark.req("R8")
@pytest.mark.parametrize("days_left, expired", [(-1, True), (0, True), (1, False)])
def test_batch_expiry_for_sale(days_left, expired):
    pharmacy = d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    drug = d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    batch = d.Batch("S-1", TODAY + timedelta(days=days_left), Decimal("1"), Decimal("2"), 5, drug, pharmacy)
    assert batch.is_expired(TODAY) is expired


# --- Правило 6: кількість у продажу за рецептом (R6.3) -----------------------------

@pytest.mark.req("R6.3")
@pytest.mark.parametrize("quantity", [1, 2])
def test_sale_quantity_within_prescribed(ctx, quantity):
    assert ctx.sales.sell("Ф-7", "E-100", quantity).quantity == quantity


@pytest.mark.req("R6.3")
def test_sale_quantity_above_prescribed(ctx):
    with pytest.raises(Refused, match="призначено лише 2"):
        ctx.sales.sell("Ф-7", "E-100", 3)


@pytest.mark.parametrize("quantity", [0, -1])
def test_sale_quantity_not_positive_is_contract_violation(ctx, quantity):
    with pytest.raises(d.ContractError):
        ctx.sales.sell("Ф-7", "E-100", quantity)


# --- Правило 7: строк дії резервування (R4) ----------------------------------------

@pytest.mark.req("R4", "R4.1")
@pytest.mark.parametrize("hours, expired", [(23, False), (24, False), (25, True)])
def test_reservation_deadline(ctx, hours, expired):
    code = reserve(ctx).code
    reservation = ctx.uow.reservations.get(code)
    moment = NOW + timedelta(hours=hours)
    if expired:
        reservation.expire(moment)
        assert reservation.state is d.ReservationState.EXPIRED
    else:
        with pytest.raises(d.TransitionError):
            reservation.expire(moment)
