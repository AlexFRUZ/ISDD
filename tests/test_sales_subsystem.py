from datetime import timedelta
from decimal import Decimal

import pytest

import pharmacy.domain as d
from conftest import NOW
from pharmacy.foundation.errors import Refused

PHONE = "+380671112233"


def ready_reservation(ctx, drug="Парацетамол", quantity=2, recipe=None):
    result = ctx.reservations.reserve(PHONE, "А-01", drug, quantity, recipe)
    ctx.preparation.prepare("Ф-7", result.code)
    return result.code


def state(ctx, code):
    ctx.uow.clear()
    return ctx.uow.reservations.get(code).state


@pytest.mark.req("R5", "R5.1", "R5.2", "R8")
def test_uc6_issues_ready_reservation_and_creates_sale(ctx):
    code = ready_reservation(ctx)
    result = ctx.reserved_sales.issue("Ф-7", code)
    assert (result.trade_name, result.quantity, result.total) == ("Парацетамол", 2, Decimal("71.00"))
    assert state(ctx, code) is d.ReservationState.ISSUED
    batch = ctx.batch("PA-1")
    assert (batch.quantity, batch.reserved) == (18, 0)
    ctx.uow.clear()
    sale = ctx.uow.sales.get(result.number)
    assert sale.customer.phone == PHONE and sale.lines[0].quantity == 2


@pytest.mark.req("R5", "R6.4")
def test_uc6_redeems_recipe_of_reserved_rx_drug(ctx):
    code = ready_reservation(ctx, "Амоксил", 1, "E-100")
    result = ctx.reserved_sales.issue("Ф-7", code)
    assert result.total == Decimal("120.00")
    assert ctx.recipe("E-100").state is d.PrescriptionState.REDEEMED


def test_uc6_flow_3a_missing_reservation(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.reserved_sales.issue("Ф-7", "R-99")
    assert refusal.value.flow == "3a"


@pytest.mark.req("R5.3")
def test_uc6_flow_3b_reservation_of_other_pharmacy(ctx):
    code = ctx.reservations.reserve(PHONE, "А-02", "Актрапід", 1, "E-102").code
    with pytest.raises(Refused) as refusal:
        ctx.reserved_sales.issue("Ф-7", code)
    assert refusal.value.flow == "3b"


@pytest.mark.req("R5.1")
def test_uc6_flow_4a_reservation_not_ready(ctx):
    code = ctx.reservations.reserve(PHONE, "А-01", "Парацетамол", 1).code
    with pytest.raises(Refused) as refusal:
        ctx.reserved_sales.issue("Ф-7", code)
    assert refusal.value.flow == "4a" and state(ctx, code) is d.ReservationState.CONFIRMED


@pytest.mark.req("R5.1")
def test_uc6_flow_4b_expired_ready_reservation(ctx):
    code = ready_reservation(ctx)
    ctx.clock["now"] = NOW + timedelta(hours=25)
    with pytest.raises(Refused) as refusal:
        ctx.reserved_sales.issue("Ф-7", code)
    assert refusal.value.flow == "4b" and state(ctx, code) is d.ReservationState.READY


@pytest.mark.req("R5.2")
def test_uc6_transaction_rolls_back_reservation_and_stock(ctx, monkeypatch):
    code = ready_reservation(ctx)

    def broken_save(_sale):
        raise RuntimeError("збій запису")

    monkeypatch.setattr(ctx.uow.sales, "save", broken_save)
    with pytest.raises(RuntimeError):
        ctx.reserved_sales.issue("Ф-7", code)
    monkeypatch.undo()
    assert state(ctx, code) is d.ReservationState.READY
    batch = ctx.batch("PA-1")
    assert (batch.quantity, batch.reserved) == (20, 2)


@pytest.mark.req("R7", "R8", "R8.1")
def test_uc8_sells_otc_using_fefo(ctx):
    result = ctx.otc_sales.sell("Ф-7", "Парацетамол", 2, "готівка")
    assert (result.series, result.total) == ("PA-0", Decimal("60.00"))
    assert ctx.batch("PA-0").quantity == 18


@pytest.mark.req("R7.1")
def test_uc8_flow_3b_rejects_prescription_drug(ctx):
    with pytest.raises(Refused, match="рецептурним") as refusal:
        ctx.otc_sales.sell("Ф-7", "Амоксил", 1)
    assert refusal.value.flow == "3b"


def test_uc8_flow_3a_unknown_drug(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.otc_sales.sell("Ф-7", "Невідомий", 1)
    assert refusal.value.flow == "3a"


@pytest.mark.req("R7.2")
@pytest.mark.parametrize("quantity, accepted", [(10, True), (11, False)])
def test_uc8_quantity_limit_boundary(ctx, quantity, accepted):
    if accepted:
        assert ctx.otc_sales.sell("Ф-7", "Парацетамол", quantity)
    else:
        with pytest.raises(Refused, match="не більше 10") as refusal:
            ctx.otc_sales.sell("Ф-7", "Парацетамол", quantity)
        assert refusal.value.flow == "4a"


def test_uc8_transaction_rolls_back_stock(ctx, monkeypatch):
    def broken_save(_sale):
        raise RuntimeError("збій запису")

    monkeypatch.setattr(ctx.uow.sales, "save", broken_save)
    with pytest.raises(RuntimeError):
        ctx.otc_sales.sell("Ф-7", "Парацетамол", 2)
    monkeypatch.undo()
    assert ctx.batch("PA-0").quantity == 20


@pytest.mark.req("R6.1", "R6.2")
def test_uc9_verifies_active_recipe(ctx):
    recipe = ctx.recipe_verification.verify("E-100", NOW.date())
    assert recipe.number == "E-100" and recipe.state is d.PrescriptionState.ACTIVE


def test_uc9_flow_3a_recipe_not_found(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.recipe_verification.verify("E-999", NOW.date())
    assert refusal.value.flow == "3a"


@pytest.mark.parametrize("number", ["E-200", "E-300", "E-301"])
def test_uc9_flow_3b_rejects_invalid_recipe(ctx, number):
    with pytest.raises(Refused) as refusal:
        ctx.recipe_verification.verify(number, NOW.date())
    assert refusal.value.flow == "3b"


def test_uc9_flow_6b_checks_drug_inn_for_reservation(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.recipe_verification.verified_for("E-100", "Insulin", NOW.date())
    assert refusal.value.flow == "6b"


def test_uc9_flow_2a_registry_unavailable(ctx):
    ctx.registry.online = False
    with pytest.raises(Refused, match="недоступний") as refusal:
        ctx.recipe_verification.verify("E-100", NOW.date())
    assert refusal.value.flow == "2a"
