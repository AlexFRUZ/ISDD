"""Тести доменної моделі: кратності, інваріанти та нормальна поведінка (ЛР 2)."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

import pharmacy.domain as d

TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 10, 0)
FAR_EXPIRY = date(2027, 11, 4)


@pytest.fixture
def pharmacy():
    return d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")


@pytest.fixture
def otc_drug():
    return d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")


@pytest.fixture
def rx_drug():
    return d.PrescriptionDrug("Амоксил", "Amoxicillin", "таблетки", "500 мг", "Київмедпрепарат")


@pytest.fixture
def batch(otc_drug, pharmacy):
    return d.Batch("S-100", FAR_EXPIRY, Decimal("20"), Decimal("35.50"), 20, otc_drug, pharmacy)


@pytest.fixture
def rx_batch(rx_drug, pharmacy):
    return d.Batch("S-200", FAR_EXPIRY, Decimal("80"), Decimal("120"), 10, rx_drug, pharmacy)


@pytest.fixture
def customer():
    return d.Customer("+380671112233", "Іваненко Марія")


@pytest.fixture
def doctor():
    return d.Doctor("Коваль Петро", "терапевт")


@pytest.fixture
def pharmacist(pharmacy):
    return d.Pharmacist("Ф-7", "Бойко Ірина", pharmacy)


def reserve(customer, batch, code="R-1", quantity=1, prescription=None):
    reservation = d.Reservation(code, NOW, quantity, customer, batch, prescription)
    reservation.confirm()
    return reservation


# --- Нормальна поведінка ---------------------------------------------------------

def test_reservation_blocks_stock_and_sets_expiry(customer, batch):
    reservation = reserve(customer, batch, quantity=2)
    assert batch.available == 18 and batch.quantity == 20
    assert reservation.expires_at == NOW + timedelta(hours=24)
    assert customer.active_reservations == [reservation]


def test_cancel_returns_stock(customer, batch):
    reservation = reserve(customer, batch, quantity=2)
    reservation.cancel()
    assert batch.available == 20 and not reservation.is_active


def test_extend_adds_24_hours(customer, batch):
    reservation = reserve(customer, batch)
    reservation.prepare()
    reservation.extend()
    assert reservation.expires_at == NOW + timedelta(hours=48)
    assert reservation.state is d.ReservationState.EXTENDED


def test_sale_total_uses_retail_price(pharmacist, batch):
    sale = d.Sale("Ч-1", NOW, d.PaymentMethod.CASH, pharmacist)
    sale.add_line(batch, 2)
    assert sale.total == Decimal("71.00") and batch.quantity == 18


def test_prescription_is_valid_on_last_day(doctor):
    recipe = d.EPrescription("E-1", TODAY - timedelta(days=30), "Amoxicillin", 2, doctor)
    assert recipe.is_valid(TODAY)


def test_redeem_marks_prescription(doctor):
    recipe = d.EPrescription("E-1", TODAY, "Amoxicillin", 2, doctor)
    recipe.redeem(2, TODAY)
    assert recipe.state is d.PrescriptionState.REDEEMED


def test_rx_drug_can_be_reserved_with_matching_prescription(customer, rx_batch, doctor):
    recipe = d.EPrescription("E-1", TODAY, "Amoxicillin", 2, doctor)
    assert reserve(customer, rx_batch, prescription=recipe).prescription is recipe


# --- Порушення кратностей та інваріантів ------------------------------------------

def test_customer_cannot_have_four_active_reservations(customer, batch):
    for number in range(3):
        reserve(customer, batch, f"R-{number}")
    with pytest.raises(d.DomainError, match="3 активні"):
        reserve(customer, batch, "R-4")


def test_cancelled_reservation_frees_customer_slot(customer, batch):
    reservations = [reserve(customer, batch, f"R-{n}") for n in range(3)]
    reservations[0].cancel()
    assert reserve(customer, batch, "R-4").is_active


@pytest.mark.parametrize("quantity", [0, 6])
def test_reservation_quantity_limits(customer, batch, quantity):
    with pytest.raises(d.DomainError, match="від 1 до 5"):
        reserve(customer, batch, quantity=quantity)


def test_cannot_reserve_more_than_available(customer, otc_drug, pharmacy):
    small = d.Batch("S-1", FAR_EXPIRY, Decimal("1"), Decimal("2"), 2, otc_drug, pharmacy)
    reservation = reserve(customer, small, quantity=3)
    assert reservation.state is d.ReservationState.CANCELLED and small.available == 2


def test_batch_cannot_block_more_than_available(batch):
    with pytest.raises(d.DomainError, match="доступно лише 20"):
        batch.block(21)


def test_rx_drug_needs_prescription_for_reservation(customer, rx_batch):
    with pytest.raises(d.DomainError, match="чинний е-рецепт"):
        reserve(customer, rx_batch)


def test_prescription_for_other_inn_is_rejected(customer, rx_batch, doctor):
    recipe = d.EPrescription("E-1", TODAY, "Ibuprofen", 2, doctor)
    with pytest.raises(d.DomainError, match="чинний е-рецепт"):
        reserve(customer, rx_batch, prescription=recipe)


def test_batch_with_short_shelf_life_cannot_be_reserved(customer, otc_drug, pharmacy):
    soon = d.Batch("S-2", TODAY + timedelta(days=29), Decimal("1"), Decimal("2"), 5, otc_drug, pharmacy)
    with pytest.raises(d.DomainError, match="менший за 30"):
        reserve(customer, soon)


def test_only_one_extension_allowed(customer, batch):
    reservation = reserve(customer, batch)
    reservation.prepare()
    reservation.extend()
    with pytest.raises(d.DomainError, match="недопустима"):
        reservation.extend()


def test_expired_batch_cannot_be_sold(pharmacist, otc_drug, pharmacy):
    old = d.Batch("S-3", TODAY, Decimal("1"), Decimal("2"), 5, otc_drug, pharmacy)
    sale = d.Sale("Ч-2", NOW, d.PaymentMethod.CARD, pharmacist)
    with pytest.raises(d.DomainError, match="строк придатності минув"):
        sale.add_line(old, 1)


def test_rx_drug_cannot_be_sold_without_prescription(pharmacist, rx_batch):
    sale = d.Sale("Ч-3", NOW, d.PaymentMethod.CARD, pharmacist)
    with pytest.raises(d.DomainError, match="лише за е-рецептом"):
        sale.add_line(rx_batch, 1)


def test_same_batch_twice_in_sale_is_rejected(pharmacist, batch):
    sale = d.Sale("Ч-4", NOW, d.PaymentMethod.CARD, pharmacist)
    sale.add_line(batch, 1)
    with pytest.raises(d.DomainError, match="вже є в чеку"):
        sale.add_line(batch, 1)


def test_empty_sale_cannot_be_completed(pharmacist):
    with pytest.raises(d.DomainError, match="щонайменше одну позицію"):
        d.Sale("Ч-5", NOW, d.PaymentMethod.CASH, pharmacist).complete()


def test_expired_prescription_cannot_be_redeemed(doctor):
    recipe = d.EPrescription("E-2", TODAY - timedelta(days=31), "Amoxicillin", 2, doctor)
    with pytest.raises(d.DomainError, match="недійсний"):
        recipe.redeem(1, TODAY)


def test_redeemed_prescription_cannot_be_redeemed_twice(doctor):
    recipe = d.EPrescription("E-3", TODAY, "Amoxicillin", 2, doctor)
    recipe.redeem(1, TODAY)
    with pytest.raises(d.DomainError, match="недійсний"):
        recipe.redeem(1, TODAY)


def test_redeem_more_than_prescribed_is_rejected(doctor):
    recipe = d.EPrescription("E-4", TODAY, "Amoxicillin", 2, doctor)
    with pytest.raises(d.DomainError, match="призначено лише 2"):
        recipe.redeem(3, TODAY)


def test_chain_needs_at_least_one_pharmacy():
    with pytest.raises(d.DomainError, match="щонайменше з однієї"):
        d.PharmacyChain("Мережа", "12345678", [])


def test_last_pharmacy_cannot_be_removed(pharmacy):
    chain = d.PharmacyChain("Мережа", "12345678", [pharmacy])
    with pytest.raises(d.DomainError, match="останню аптеку"):
        chain.remove_pharmacy(pharmacy)


def test_delivery_needs_at_least_one_batch():
    with pytest.raises(d.DomainError, match="щонайменше одну партію"):
        d.Delivery("Н-1", TODAY, d.Supplier("Оптима", "+380441110000"), [])


@pytest.mark.parametrize("share", [Decimal("-0.1"), Decimal("1.1")])
def test_reimbursement_share_range(doctor, share):
    with pytest.raises(d.DomainError, match="реімбурсації"):
        d.EPrescription("E-5", TODAY, "Amoxicillin", 1, doctor, reimbursement_share=share)


def test_pharmacy_can_be_removed_while_others_remain(pharmacy):
    other = d.Pharmacy("А-02", "вул. Проскурівська, 7", "Хмельницький", "+380382000002", "8:00-22:00")
    chain = d.PharmacyChain("Мережа", "12345678", [pharmacy, other])
    chain.remove_pharmacy(pharmacy)
    assert chain.pharmacies == [other]


def test_delivery_registers_itself_at_supplier(batch):
    supplier = d.Supplier("Оптима", "+380441110000")
    delivery = d.Delivery("Н-1", TODAY, supplier, [batch])
    assert supplier.deliveries == [delivery]


def test_finished_reservation_can_be_archived(customer, batch):
    reservation = reserve(customer, batch)
    reservation.cancel()
    reservation.archive()
    assert reservation.state is d.ReservationState.ARCHIVED
