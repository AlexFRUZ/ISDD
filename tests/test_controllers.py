from datetime import timedelta
from decimal import Decimal

import pytest

from conftest import NOW
from pharmacy.domain import PrescriptionState, ReservationState
from pharmacy.foundation.errors import Refused

PHONE = "+380671112233"


def reserve(ctx, drug="Парацетамол", quantity=1, recipe=None, phone=PHONE, pharmacy="А-01"):
    return ctx.reservations.reserve(phone, pharmacy, drug, quantity, recipe)


@pytest.mark.req("R6", "R6.1", "R6.4")
def test_sale_normal_flow(ctx):
    result = ctx.sales.sell("Ф-7", "E-100", 2)
    assert result.total == Decimal("240.00") and result.series == "AM-1"
    assert ctx.batch("AM-1").quantity == 8
    assert ctx.recipe("E-100").state is PrescriptionState.REDEEMED
    assert ctx.uow.sales.get(result.number).prescription.number == "E-100"


@pytest.mark.req("R6.5")
def test_sale_with_reimbursement(ctx):
    assert ctx.sales.sell("Ф-7", "E-101", 2).total == Decimal("180.00")


@pytest.mark.req("R6.2")
def test_sale_recipe_not_found(ctx):
    with pytest.raises(Refused, match="не знайдено") as refusal:
        ctx.sales.sell("Ф-7", "E-999", 1)
    assert refusal.value.flow == "3a"


@pytest.mark.req("R6.2")
@pytest.mark.parametrize("number, reason", [
    ("E-200", "минув строк дії"), ("E-300", "погашений"), ("E-301", "скасований"),
])
def test_sale_recipe_invalid(ctx, number, reason):
    with pytest.raises(Refused, match=reason) as refusal:
        ctx.sales.sell("Ф-7", number, 1)
    assert refusal.value.flow == "3b"


@pytest.mark.req("R6.3")
def test_sale_quantity_above_prescribed(ctx):
    with pytest.raises(Refused, match="призначено лише 2") as refusal:
        ctx.sales.sell("Ф-7", "E-100", 3)
    assert refusal.value.flow == "4a"


@pytest.mark.req("R8")
def test_sale_no_batch_suggests_other_pharmacy(ctx):
    with pytest.raises(Refused, match="А-02") as refusal:
        ctx.sales.sell("Ф-7", "E-102", 1)
    assert refusal.value.flow == "5a"


@pytest.mark.req("R6.4")
def test_sale_registry_down_changes_nothing(ctx):
    ctx.registry.online = False
    with pytest.raises(Refused, match="недоступний") as refusal:
        ctx.sales.sell("Ф-7", "E-100", 1)
    assert refusal.value.flow == "6a"
    assert ctx.batch("AM-1").quantity == 10
    assert ctx.recipe("E-100").state is PrescriptionState.ACTIVE


def test_sale_unknown_pharmacist(ctx):
    with pytest.raises(Refused, match="Фармацевта"):
        ctx.sales.sell("Ф-0", "E-100", 1)


@pytest.mark.req("R2", "R2.3")
def test_reserve_normal_flow(ctx):
    result = reserve(ctx, quantity=2)
    reservation = ctx.uow.reservations.get(result.code)
    assert reservation.state is ReservationState.CONFIRMED
    assert ctx.batch("PA-1").available == 18 and result.expires_at == NOW + timedelta(hours=24)


@pytest.mark.req("R2.5")
def test_reserve_skips_batch_with_short_shelf_life(ctx):
    assert reserve(ctx).series == "PA-1"


@pytest.mark.req("R2.1")
def test_reserve_limit_of_active_reservations(ctx):
    for _ in range(3):
        reserve(ctx)
    with pytest.raises(Refused, match="3 активні") as refusal:
        reserve(ctx)
    assert refusal.value.flow == "3a"


@pytest.mark.req("R2.2")
@pytest.mark.parametrize("quantity", [0, 7])
def test_reserve_quantity_limits(ctx, quantity):
    with pytest.raises(Refused, match="від 1 до 6"):
        reserve(ctx, quantity=quantity)


def test_reserve_no_suitable_batch(ctx):
    with pytest.raises(Refused, match="немає придатної партії") as refusal:
        reserve(ctx, drug="Актрапід")
    assert refusal.value.flow == "5a"


@pytest.mark.req("R2.4")
def test_reserve_rx_drug_needs_recipe(ctx):
    with pytest.raises(Refused, match="потрібен номер") as refusal:
        reserve(ctx, drug="Амоксил")
    assert refusal.value.flow == "6a"


@pytest.mark.req("R2.4")
@pytest.mark.parametrize("recipe", ["E-999", "E-200", "E-102"])
def test_reserve_rx_drug_rejects_unsuitable_recipe(ctx, recipe):
    with pytest.raises(Refused, match="не підходить") as refusal:
        reserve(ctx, drug="Амоксил", recipe=recipe)
    assert refusal.value.flow == "6b"


@pytest.mark.req("R2.4")
def test_reserve_rx_drug_with_valid_recipe(ctx):
    assert reserve(ctx, drug="Амоксил", recipe="E-100").series == "AM-1"


def test_repeated_customer_is_reused(ctx):
    reserve(ctx)
    reserve(ctx)
    assert len(ctx.uow.reservations.find_active_by_customer(PHONE)) == 2
