from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

import pharmacy.domain as d
from conftest import NOW, TODAY
from pharmacy.controllers.warehouse import DeliveryLine
from pharmacy.foundation.errors import ContractError, Refused

SUPPLIER = "Оптима-Фарм"


def line(series="PA-2", expiry=None, quantity=30, drug="Парацетамол", purchase="20", retail="35.50"):
    return DeliveryLine(drug, series, expiry or TODAY + timedelta(days=365), Decimal(purchase),
                        Decimal(retail), quantity)


def stock(ctx, series, pharmacy="А-01", drug="Парацетамол"):
    ctx.uow.clear()
    return ctx.uow.batches.get((pharmacy, drug, series))



@pytest.mark.req("R9", "R9.3")
def test_uc10_receives_delivery_into_pharmacy_stock(ctx):
    result = ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line(), line("AM-9", drug="Амоксил", quantity=5)])
    assert result.packs == 35 and result.pharmacy_number == "А-01"
    batch = stock(ctx, "PA-2")
    assert (batch.quantity, batch.reserved, batch.retail_price) == (30, 0, Decimal("35.50"))
    assert stock(ctx, "AM-9", drug="Амоксил").quantity == 5
    ctx.uow.clear()
    delivery = ctx.uow.deliveries.get("Н-10")
    assert delivery.supplier.name == SUPPLIER and len(delivery.batches) == 2
    assert delivery.delivery_date == TODAY


@pytest.mark.req("R9.1")
def test_uc10_flow_3a_duplicate_invoice(ctx):
    ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line()])
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-3")])
    assert refusal.value.flow == "3a"
    assert stock(ctx, "PA-3") is None


def test_uc10_flow_3b_unknown_supplier(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("З-1", "Н-10", "Невідомий", [line()])
    assert refusal.value.flow == "3b"


def test_uc10_flow_4a_unknown_drug(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line(drug="Невідомий")])
    assert refusal.value.flow == "4a"


@pytest.mark.req("R9.2")
@pytest.mark.parametrize("days, accepted", [(0, False), (1, True)])
def test_uc10_expiry_boundary_today_is_refused(ctx, days, accepted):
    lines = [line(expiry=TODAY + timedelta(days=days))]
    if accepted:
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, lines)
        assert stock(ctx, "PA-2").quantity == 30
    else:
        with pytest.raises(Refused) as refusal:
            ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, lines)
        assert refusal.value.flow == "4b"


@pytest.mark.req("R9.2")
def test_uc10_flow_5a_series_already_in_pharmacy(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-1")])
    assert refusal.value.flow == "5a"


@pytest.mark.req("R9.2")
def test_uc10_flow_5a_series_repeated_inside_invoice(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-2"), line("PA-2")])
    assert refusal.value.flow == "5a"


@pytest.mark.req("R9.2")
def test_uc10_flow_5b_series_with_other_expiry(ctx):
    other_date = TODAY + timedelta(days=100)
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("З-2", "Н-10", SUPPLIER, [line("PA-1", expiry=other_date)])
    assert refusal.value.flow == "5b"


@pytest.mark.req("R9.2")
def test_uc10_same_series_in_other_pharmacy_with_same_expiry_is_accepted(ctx):
    same_date = stock(ctx, "PA-1").expiry_date
    ctx.deliveries.receive("З-2", "Н-10", SUPPLIER, [line("PA-1", expiry=same_date)])
    assert stock(ctx, "PA-1", "А-02").quantity == 30
    assert stock(ctx, "PA-1").quantity == 20


@pytest.mark.req("R9.3")
def test_uc10_rejected_line_leaves_no_partial_delivery(ctx):
    with pytest.raises(Refused):
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-2"), line("PA-1")])
    assert stock(ctx, "PA-2") is None
    assert ctx.uow.deliveries.get("Н-10") is None


@pytest.mark.req("R9")
def test_uc10_unknown_manager(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.deliveries.receive("Ф-7", "Н-10", SUPPLIER, [line()])
    assert refusal.value.flow == "зв"


@pytest.mark.req("R9.2")
@pytest.mark.parametrize("bad", [dict(quantity=0), dict(quantity=-1), dict(retail="-1")])
def test_uc10_contract_rejects_invalid_numbers(ctx, bad):
    with pytest.raises(ContractError):
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line(**bad)])


def test_uc10_contract_rejects_empty_invoice(ctx):
    with pytest.raises(ContractError):
        ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [])
    with pytest.raises(ContractError):
        ctx.deliveries.receive("З-1", " ", SUPPLIER, [line()])


def test_uc10_received_batch_is_sold_by_fefo_after_older_ones(ctx):
    ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-2", expiry=TODAY + timedelta(days=5))])
    ctx.otc_sales.sell("Ф-7", "Парацетамол", 1)
    assert stock(ctx, "PA-2").quantity == 29



@pytest.mark.req("R10", "R10.2")
def test_uc11_writes_off_whole_free_stock_and_stores_act(ctx):
    result = ctx.write_offs.write_off("З-1", "Парацетамол", "PA-0", "строк придатності минув")
    assert (result.written_off, result.remaining, result.number) == (20, 0, "С-1")
    assert stock(ctx, "PA-0").quantity == 0
    acts = ctx.uow.write_offs.find_by_pharmacy("А-01")
    assert [(a.quantity, a.reason, a.manager.personnel_number) for a in acts] == \
        [(20, d.WriteOffReason.EXPIRED, "З-1")]
    assert acts[0].written_at == NOW


@pytest.mark.req("R10")
def test_uc11_partial_write_off(ctx):
    result = ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "пошкодження", 5)
    assert (result.written_off, result.remaining) == (5, 15)


@pytest.mark.req("R10.1")
def test_uc11_reserved_quantity_cannot_be_written_off(ctx):
    ctx.reservations.reserve("+380671112233", "А-01", "Парацетамол", 2)
    assert stock(ctx, "PA-1").reserved == 2
    result = ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "брак виробника")
    assert (result.written_off, result.remaining) == (18, 2)
    batch = stock(ctx, "PA-1")
    assert (batch.quantity, batch.reserved) == (2, 2)
    with pytest.raises(Refused) as refusal:
        ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "брак виробника")
    assert refusal.value.flow == "5b"


@pytest.mark.req("R10.1")
@pytest.mark.parametrize("quantity, accepted", [(20, True), (21, False)])
def test_uc11_quantity_boundary(ctx, quantity, accepted):
    if accepted:
        assert ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "інша причина", quantity).remaining == 0
    else:
        with pytest.raises(Refused) as refusal:
            ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "інша причина", quantity)
        assert refusal.value.flow == "5b"


def test_uc11_flow_3a_batch_of_other_pharmacy_is_not_visible(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.write_offs.write_off("З-2", "Парацетамол", "PA-1", "пошкодження")
    assert refusal.value.flow == "3a"
    assert stock(ctx, "PA-1").quantity == 20


@pytest.mark.req("R10.2")
def test_uc11_flow_4a_reason_outside_list(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "захотілося")
    assert refusal.value.flow == "4a"
    assert stock(ctx, "PA-1").quantity == 20
    assert ctx.uow.write_offs.find_by_pharmacy("А-01") == []


def test_uc11_flow_5a_empty_batch(ctx):
    ctx.write_offs.write_off("З-1", "Парацетамол", "PA-0", "пошкодження")
    with pytest.raises(Refused) as refusal:
        ctx.write_offs.write_off("З-1", "Парацетамол", "PA-0", "пошкодження")
    assert refusal.value.flow == "5a"


def test_uc11_contract_rejects_zero_quantity(ctx):
    with pytest.raises(ContractError):
        ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "пошкодження", 0)


def test_uc11_numbers_acts_sequentially(ctx):
    first = ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "пошкодження", 1)
    second = ctx.write_offs.write_off("З-1", "Парацетамол", "PA-1", "пошкодження", 1)
    assert (first.number, second.number) == ("С-1", "С-2")


def test_uc11_unknown_manager(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.write_offs.write_off("Ф-7", "Парацетамол", "PA-1", "пошкодження")
    assert refusal.value.flow == "зв"



def test_uc12_lists_batches_expiring_within_30_days(ctx):
    rows = ctx.expiry.expiring("З-1")
    assert [(r.trade_name, r.series, r.days_left) for r in rows] == [("Парацетамол", "PA-0", 10)]


@pytest.mark.req("R13")
@pytest.mark.parametrize("days_left, listed", [(30, True), (31, False)])
def test_uc12_boundary_30_and_31_days(ctx, days_left, listed):
    ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-9", TODAY + timedelta(days=days_left))])
    series = [r.series for r in ctx.expiry.expiring("З-1")]
    assert ("PA-9" in series) is listed


@pytest.mark.req("R13.1")
def test_uc12_includes_expired_batches_with_stock_sorted_by_expiry(ctx):
    ctx.uow.clear()
    batch = ctx.uow.batches.get(("А-01", "Парацетамол", "PA-0"))
    batch.expiry_date = TODAY - timedelta(days=1)
    ctx.uow.batches.save(batch)
    ctx.deliveries.receive("З-1", "Н-10", SUPPLIER, [line("PA-9", TODAY + timedelta(days=3))])
    rows = ctx.expiry.expiring("З-1")
    assert [(r.series, r.expired) for r in rows] == [("PA-0", True), ("PA-9", False)]


@pytest.mark.req("R13.1")
def test_uc12_hides_batches_without_stock(ctx):
    ctx.write_offs.write_off("З-1", "Парацетамол", "PA-0", "строк придатності минув")
    assert ctx.expiry.expiring("З-1") == []


@pytest.mark.req("R13")
def test_uc12_shows_only_own_pharmacy(ctx):
    assert ctx.expiry.expiring("З-2") == []


def test_uc12_custom_horizon_and_contract(ctx):
    assert [r.series for r in ctx.expiry.expiring("З-1", days=100)] == ["PA-0", "AM-1"]
    with pytest.raises(ContractError):
        ctx.expiry.expiring("З-1", days=-1)


def test_uc12_shows_reserved_quantity(ctx):
    ctx.reservations.reserve("+380671112233", "А-01", "Парацетамол", 2)
    rows = {r.series: r for r in ctx.expiry.expiring("З-1", days=400)}
    assert (rows["PA-1"].quantity, rows["PA-1"].reserved) == (20, 2)



def sell(ctx, drug="Парацетамол", quantity=2, when=NOW):
    ctx.clock["now"] = when
    ctx.otc_sales.sell("Ф-7", drug, quantity)
    ctx.clock["now"] = NOW


@pytest.mark.req("R11")
def test_uc13_sums_sales_per_pharmacy(ctx):
    sell(ctx, quantity=2)          # PA-0 по 30.00 -> 60.00
    sell(ctx, quantity=1)          # PA-0 -> 30.00
    report = ctx.sales_reports.report("Д-1", TODAY, TODAY)
    first = next(r for r in report.rows if r.pharmacy_number == "А-01")
    assert (first.sales_count, first.packs, first.revenue, first.average_check) == (2, 3, Decimal("90.00"), Decimal("45.00"))
    assert (report.sales_count, report.packs, report.revenue) == (2, 3, Decimal("90.00"))
    assert [r.pharmacy_number for r in report.rows] == ["А-01", "А-02"]


@pytest.mark.req("R11.1")
def test_uc13_manager_sees_only_own_pharmacy(ctx):
    sell(ctx)
    own = ctx.sales_reports.report("З-1", TODAY, TODAY)
    assert [r.pharmacy_number for r in own.rows] == ["А-01"]
    other = ctx.sales_reports.report("З-2", TODAY, TODAY)
    assert [r.pharmacy_number for r in other.rows] == ["А-02"] and other.sales_count == 0


@pytest.mark.req("R11.1")
def test_uc13_manager_cannot_request_other_pharmacy(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.sales_reports.report("З-1", TODAY, TODAY, "А-02")
    assert refusal.value.flow == "4b"


def test_uc13_director_can_narrow_to_one_pharmacy(ctx):
    sell(ctx)
    report = ctx.sales_reports.report("Д-1", TODAY, TODAY, "А-01")
    assert [r.pharmacy_number for r in report.rows] == ["А-01"] and report.sales_count == 1


def test_uc13_flow_4a_unknown_pharmacy(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.sales_reports.report("Д-1", TODAY, TODAY, "А-99")
    assert refusal.value.flow == "4a"


@pytest.mark.req("R11.2")
def test_uc13_period_includes_both_boundary_days_completely(ctx):
    sell(ctx, quantity=1, when=datetime(2026, 11, 3, 0, 0, 0))
    sell(ctx, quantity=1, when=datetime(2026, 11, 3, 23, 59, 59))
    sell(ctx, quantity=1, when=datetime(2026, 11, 4, 23, 59, 59))
    sell(ctx, quantity=1, when=datetime(2026, 11, 2, 23, 59, 59))
    sell(ctx, quantity=1, when=datetime(2026, 11, 5, 0, 0, 0))
    report = ctx.sales_reports.report("Д-1", date(2026, 11, 3), date(2026, 11, 4))
    assert report.sales_count == 3


@pytest.mark.req("R11")
def test_uc13_flow_3a_reversed_period(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.sales_reports.report("Д-1", TODAY, TODAY - timedelta(days=1))
    assert refusal.value.flow == "3a"


def test_uc13_empty_period_gives_zero_rows(ctx):
    report = ctx.sales_reports.report("Д-1", TODAY, TODAY)
    assert report.sales_count == 0 and report.revenue == Decimal("0.00")
    assert all(r.average_check == Decimal("0.00") for r in report.rows)


def test_uc13_unknown_user_and_pharmacist_is_not_allowed(ctx):
    for number in ("Х-1", "Ф-7"):
        with pytest.raises(Refused) as refusal:
            ctx.sales_reports.report(number, TODAY, TODAY)
        assert refusal.value.flow == "зв"


@pytest.mark.req("R11")
def test_uc13_reimbursed_sale_counts_amount_paid_by_customer(ctx):
    ctx.sales.sell("Ф-7", "E-101", 2)
    report = ctx.sales_reports.report("Д-1", TODAY, TODAY)
    assert report.revenue == Decimal("180.00") and report.packs == 2
