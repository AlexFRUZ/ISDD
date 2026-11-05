from datetime import date, datetime
from decimal import Decimal

import pytest

import cli
from demo_data import build_world
from prescription_sale import SaleRefused

from domain import PrescriptionState

NOW = datetime(2026, 11, 4, 10, 0)


@pytest.fixture
def world():
    return build_world(date(2026, 11, 4))


@pytest.mark.req("R6", "R6.1", "R6.4")
def test_normal_flow_creates_sale_and_redeems_recipe(world):
    sale = world.service.sell("E-100", 2, NOW)
    assert sale.total == Decimal("240.00")
    assert world.amoxicillin_batch.quantity == 8
    assert world.registry.find("E-100").state is PrescriptionState.REDEEMED


@pytest.mark.req("R8.1")
def test_normal_flow_picks_batch_with_nearest_expiry(world):
    assert world.service.sell("E-100", 1, NOW).lines[0].batch.series == "AM-1"


@pytest.mark.req("R6.5")
def test_reimbursement_reduces_amount_to_pay(world):
    assert world.service.sell("E-101", 2, NOW).total == Decimal("180.00")


@pytest.mark.req("R6.2")
def test_flow_3a_recipe_not_found(world):
    with pytest.raises(SaleRefused, match="не знайдено") as refusal:
        world.service.sell("E-999", 1, NOW)
    assert refusal.value.flow == "3a"


@pytest.mark.req("R6.2")
@pytest.mark.parametrize("number, reason", [
    ("E-200", "минув строк дії"),
    ("E-300", "погашений"),
    ("E-301", "скасований"),
])
def test_flow_3b_recipe_invalid(world, number, reason):
    with pytest.raises(SaleRefused, match=reason) as refusal:
        world.service.sell(number, 1, NOW)
    assert refusal.value.flow == "3b"


@pytest.mark.req("R6.3")
def test_flow_4a_quantity_above_prescribed(world):
    with pytest.raises(SaleRefused, match="призначено лише 2") as refusal:
        world.service.sell("E-100", 3, NOW)
    assert refusal.value.flow == "4a"
    assert world.registry.find("E-100").state is PrescriptionState.ACTIVE


@pytest.mark.req("R8")
def test_flow_5a_no_batch_suggests_other_pharmacy(world):
    with pytest.raises(SaleRefused, match="А-02") as refusal:
        world.service.sell("E-102", 1, NOW)
    assert refusal.value.flow == "5a"


@pytest.mark.req("R6.4")
def test_flow_6a_registry_down_changes_nothing(world):
    world.registry.online = False
    with pytest.raises(SaleRefused, match="недоступний") as refusal:
        world.service.sell("E-100", 1, NOW)
    assert refusal.value.flow == "6a"
    assert world.amoxicillin_batch.quantity == 10
    assert world.registry.find("E-100").state is PrescriptionState.ACTIVE


def test_cli_prints_sale(capsys):
    assert cli.main(["sell", "--recipe", "E-100", "--qty", "1"]) == 0
    assert "до сплати 120.00 грн" in capsys.readouterr().out


def test_cli_prints_refusal_and_returns_error_code(capsys):
    assert cli.main(["sell", "--recipe", "E-999"]) == 1
    assert "потік 3a" in capsys.readouterr().out
