"""Інтеграційні тести UC7 на основі його опису (ЛР 7, завдання 3).

Кожен тест проходить через контролер, доменні класи й репозиторій SQLite у пам'яті, а
результат перевіряє прямим SQL-запитом. Номери потоків збігаються з lab3/uc7_description.md.
"""
from decimal import Decimal

import pytest

from pharmacy.foundation.errors import Refused


def value(ctx, sql, *params):
    return ctx.uow.connection.execute(sql, params).fetchone()[0]


def stock(ctx, series):
    return value(ctx, "SELECT quantity FROM batch WHERE series = ?", series)


def recipe_state(ctx, number):
    return value(ctx, "SELECT state FROM prescription WHERE number = ?", number)


def sales_count(ctx):
    return value(ctx, "SELECT count(*) FROM sale")


@pytest.mark.req("R6", "R6.1", "R6.4", "R8.1")
def test_normal_flow(sqlite_ctx):
    result = sqlite_ctx.sales.sell("Ф-7", "E-100", 2)
    assert (result.series, result.total) == ("AM-1", Decimal("240.00"))
    assert stock(sqlite_ctx, "AM-1") == 8
    assert recipe_state(sqlite_ctx, "E-100") == "погашений"
    assert value(sqlite_ctx, "SELECT total_kop FROM sale WHERE number = ?", result.number) == 24000
    assert value(sqlite_ctx, "SELECT quantity FROM sale_line WHERE sale_number = ?", result.number) == 2


@pytest.mark.req("R6.5")
def test_normal_flow_with_reimbursement(sqlite_ctx):
    result = sqlite_ctx.sales.sell("Ф-7", "E-101", 2)
    assert value(sqlite_ctx, "SELECT total_kop FROM sale WHERE number = ?", result.number) == 18000


def assert_nothing_changed(ctx):
    assert sales_count(ctx) == 0 and stock(ctx, "AM-1") == 10


@pytest.mark.req("R6.2")
def test_flow_3a_recipe_not_found(sqlite_ctx):
    with pytest.raises(Refused) as refusal:
        sqlite_ctx.sales.sell("Ф-7", "E-999", 1)
    assert refusal.value.flow == "3a"
    assert_nothing_changed(sqlite_ctx)


@pytest.mark.req("R6.2")
@pytest.mark.parametrize("number", ["E-200", "E-300", "E-301"])
def test_flow_3b_recipe_invalid(sqlite_ctx, number):
    with pytest.raises(Refused) as refusal:
        sqlite_ctx.sales.sell("Ф-7", number, 1)
    assert refusal.value.flow == "3b"
    assert_nothing_changed(sqlite_ctx)


@pytest.mark.req("R6.3")
def test_flow_4a_quantity_above_prescribed(sqlite_ctx):
    with pytest.raises(Refused) as refusal:
        sqlite_ctx.sales.sell("Ф-7", "E-100", 3)
    assert refusal.value.flow == "4a"
    assert recipe_state(sqlite_ctx, "E-100") == "активний"
    assert_nothing_changed(sqlite_ctx)


@pytest.mark.req("R8", "R8.1")
def test_flow_5a_no_batch_shows_other_pharmacy(sqlite_ctx):
    with pytest.raises(Refused, match="А-02") as refusal:
        sqlite_ctx.sales.sell("Ф-7", "E-102", 1)
    assert refusal.value.flow == "5a"
    assert recipe_state(sqlite_ctx, "E-102") == "активний"


@pytest.mark.req("R8")
def test_flow_5a_no_other_pharmacy_has_it(sqlite_ctx):
    sqlite_ctx.uow.connection.execute("UPDATE batch SET quantity = 0 WHERE series = 'IN-1'")
    with pytest.raises(Refused) as refusal:
        sqlite_ctx.sales.sell("Ф-7", "E-102", 1)
    assert "Препарат є в аптеках" not in str(refusal.value)


@pytest.mark.req("R6.4")
def test_flow_6a_registry_unavailable(sqlite_ctx):
    sqlite_ctx.registry.online = False
    with pytest.raises(Refused) as refusal:
        sqlite_ctx.sales.sell("Ф-7", "E-100", 1)
    assert refusal.value.flow == "6a"
    assert recipe_state(sqlite_ctx, "E-100") == "активний"
    assert_nothing_changed(sqlite_ctx)


@pytest.mark.req("R6.2")
def test_recipe_cannot_be_used_twice(sqlite_ctx):
    sqlite_ctx.sales.sell("Ф-7", "E-100", 1)
    with pytest.raises(Refused, match="погашений"):
        sqlite_ctx.sales.sell("Ф-7", "E-100", 1)
    assert sales_count(sqlite_ctx) == 1
