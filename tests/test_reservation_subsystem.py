from datetime import timedelta
from decimal import Decimal

import pytest

import pharmacy.domain as d
from conftest import NOW
from pharmacy.controllers.reservation.reserve_controller import ReservationController
from pharmacy.foundation.errors import Refused

PHONE = "+380671112233"
OTHER_PHONE = "+380670000000"


def reserve(ctx, quantity=2, phone=PHONE):
    return ctx.reservations.reserve(phone, "А-01", "Парацетамол", quantity).code


def reserve_at_other_pharmacy(ctx):
    return ctx.reservations.reserve(PHONE, "А-02", "Актрапід", 1, "E-102").code


def state(ctx, code):
    ctx.uow.clear()
    return ctx.uow.reservations.get(code).state


def ready(ctx):
    code = reserve(ctx)
    ctx.preparation.prepare("Ф-7", code)
    return code


@pytest.mark.req("R3", "R3.2")
def test_uc3_normal_flow_returns_stock(ctx):
    code = reserve(ctx)
    assert ctx.batch("PA-1").available == 18
    assert ctx.cancellation.cancel(PHONE, code).state == "Скасоване"
    assert ctx.batch("PA-1").available == 20
    assert state(ctx, code) is d.ReservationState.CANCELLED


@pytest.mark.req("R3")
def test_uc3_frees_slot_for_new_reservation(ctx):
    codes = [reserve(ctx, 1) for _ in range(3)]
    ctx.cancellation.cancel(PHONE, codes[0])
    assert reserve(ctx, 1)


@pytest.mark.req("R3.1")
def test_uc3_flow_3a_foreign_reservation(ctx):
    code = reserve(ctx)
    with pytest.raises(Refused, match="не знайдено") as refusal:
        ctx.cancellation.cancel(OTHER_PHONE, code)
    assert refusal.value.flow == "3a"
    assert state(ctx, code) is d.ReservationState.CONFIRMED


@pytest.mark.req("R3.1")
def test_uc3_flow_3a_missing_reservation(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.cancellation.cancel(PHONE, "R-99")
    assert refusal.value.flow == "3a"


@pytest.mark.req("R3")
def test_uc3_flow_3b_already_finished(ctx):
    code = reserve(ctx)
    ctx.cancellation.cancel(PHONE, code)
    with pytest.raises(Refused, match="Скасоване") as refusal:
        ctx.cancellation.cancel(PHONE, code)
    assert refusal.value.flow == "3b"
    assert ctx.batch("PA-1").available == 20


@pytest.mark.req("R12", "R12.1")
def test_uc4_normal_flow_notifies_customer(ctx):
    code = reserve(ctx)
    status = ctx.preparation.prepare("Ф-7", code)
    assert status.state == "Готове" and status.notified
    assert ctx.sms.sent[0][0] == PHONE and code in ctx.sms.sent[0][1]
    ctx.uow.clear()
    assert ctx.uow.reservations.get(code).customer_notified


def test_uc4_unknown_pharmacist(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.preparation.prepare("Ф-0", reserve(ctx))
    assert refusal.value.flow == "пм"


def test_uc4_flow_3a_missing_reservation(ctx):
    with pytest.raises(Refused) as refusal:
        ctx.preparation.prepare("Ф-7", "R-99")
    assert refusal.value.flow == "3a"


def test_uc4_flow_3b_other_pharmacy(ctx):
    code = reserve_at_other_pharmacy(ctx)
    with pytest.raises(Refused, match="іншій аптеці") as refusal:
        ctx.preparation.prepare("Ф-7", code)
    assert refusal.value.flow == "3b"
    assert state(ctx, code) is d.ReservationState.CONFIRMED


def test_uc4_flow_4a_already_prepared(ctx):
    code = ready(ctx)
    with pytest.raises(Refused, match="не очікує збирання") as refusal:
        ctx.preparation.prepare("Ф-7", code)
    assert refusal.value.flow == "4a"
    assert len(ctx.sms.sent) == 1


@pytest.mark.req("R12.1")
def test_uc4_flow_5a_sms_gateway_down(ctx):
    ctx.sms.online = False
    code = reserve(ctx)
    status = ctx.preparation.prepare("Ф-7", code)
    assert status.state == "Готове" and not status.notified
    ctx.uow.clear()
    assert not ctx.uow.reservations.get(code).customer_notified


@pytest.mark.req("R4.2")
def test_uc5_normal_flow_adds_24_hours(ctx):
    code = ready(ctx)
    status = ctx.extension.extend("Ф-7", code)
    assert status.state == "Продовжене" and status.expires_at == NOW + timedelta(hours=48)


@pytest.mark.req("R4.2")
def test_uc5_flow_4a_only_once(ctx):
    code = ready(ctx)
    ctx.extension.extend("Ф-7", code)
    with pytest.raises(Refused, match="вже продовжено") as refusal:
        ctx.extension.extend("Ф-7", code)
    assert refusal.value.flow == "4a"


@pytest.mark.req("R4.2")
def test_uc5_flow_4b_not_ready(ctx):
    code = reserve(ctx)
    with pytest.raises(Refused, match="лише готове") as refusal:
        ctx.extension.extend("Ф-7", code)
    assert refusal.value.flow == "4b"


def test_uc5_flow_3b_other_pharmacy(ctx):
    code = reserve_at_other_pharmacy(ctx)
    with pytest.raises(Refused) as refusal:
        ctx.extension.extend("Ф-7", code)
    assert refusal.value.flow == "3b"


@pytest.mark.req("R4", "R4.1")
@pytest.mark.parametrize("hours, expired", [(23, False), (24, False), (25, True)])
def test_overdue_boundary(ctx, hours, expired):
    code = reserve(ctx)
    ctx.clock["now"] = NOW + timedelta(hours=hours)
    assert ctx.expiration.expire_overdue() == ([code] if expired else [])
    assert ctx.batch("PA-1").available == (20 if expired else 18)


@pytest.mark.req("R4")
def test_extended_reservation_lives_48_hours(ctx):
    code = ready(ctx)
    ctx.extension.extend("Ф-7", code)
    ctx.clock["now"] = NOW + timedelta(hours=47)
    assert ctx.expiration.expire_overdue() == []
    ctx.clock["now"] = NOW + timedelta(hours=49)
    assert ctx.expiration.expire_overdue() == [code]


@pytest.mark.req("R4")
def test_finished_reservations_are_not_expired_again(ctx):
    code = reserve(ctx)
    ctx.cancellation.cancel(PHONE, code)
    ctx.clock["now"] = NOW + timedelta(days=5)
    assert ctx.expiration.expire_overdue() == []


class StubSalesVerifier:
    def __init__(self, recipe):
        self.recipe = recipe
        self.calls = []

    def verified_for(self, number, inn, today):
        self.calls.append((number, inn, today))
        return self.recipe


@pytest.mark.req("R2.4")
def test_integration_rx_reservation_asks_sales_interface(ctx):
    recipe = ctx.uow.prescriptions.get("E-100")
    stub = StubSalesVerifier(recipe)
    controller = ReservationController(ctx.uow, stub, lambda: NOW)
    result = controller.reserve(PHONE, "А-01", "Амоксил", 1, "E-100")
    assert stub.calls == [("E-100", "Amoxicillin", NOW.date())]
    ctx.uow.clear()
    assert ctx.uow.reservations.get(result.code).prescription.number == "E-100"


def test_integration_otc_reservation_does_not_ask_sales_interface(ctx):
    stub = StubSalesVerifier(None)
    ReservationController(ctx.uow, stub, lambda: NOW).reserve(PHONE, "А-01", "Парацетамол", 1)
    assert stub.calls == []


@pytest.mark.req("R5")
def test_integration_provider_gives_reservation_to_sales(ctx):
    code = ready(ctx)
    assert ctx.provider.find(code).state is d.ReservationState.READY
    assert ctx.provider.find("R-99") is None


@pytest.mark.req("R5")
def test_integration_provider_completes_issue_for_sales(ctx):
    code = ready(ctx)
    with ctx.uow.transaction():
        ctx.provider.complete_issue(ctx.provider.find(code), NOW + timedelta(hours=1))
    assert state(ctx, code) is d.ReservationState.ISSUED
    batch = ctx.batch("PA-1")
    assert (batch.quantity, batch.reserved) == (18, 0)


def test_domain_helpers():
    pharmacy = d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    drug = d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    batch = d.Batch("S-1", NOW.date() + timedelta(days=365), Decimal("1"),
                    Decimal("2"), 5, drug, pharmacy)
    reservation = d.Customer(PHONE, "").create_reservation("R-1", NOW, 1, batch)
    assert reservation.belongs_to(PHONE) and not reservation.belongs_to(OTHER_PHONE)
    assert reservation.is_at_pharmacy("А-01") and not reservation.is_at_pharmacy("А-02")
    assert not reservation.is_overdue(NOW + timedelta(days=9))
