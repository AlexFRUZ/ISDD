from datetime import date, datetime
from decimal import Decimal

import pytest

import pharmacy.domain as d

NOW = datetime(2026, 11, 4, 10, 0)


@pytest.fixture
def batch():
    pharmacy = d.Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    drug = d.OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    return d.Batch("S-1", date(2027, 11, 4), Decimal("1"), Decimal("100.00"), 10, drug, pharmacy)


def checkout(batch, policy):
    pharmacist = d.Pharmacist("Ф-7", "Бойко Ірина", batch.pharmacy)
    sale = d.Sale("Ч-1", NOW, d.PaymentMethod.CARD, pharmacist, pricing=policy)
    sale.add_line(batch, 2)
    sale.complete()
    return sale.total


@pytest.mark.parametrize("policy, expected", [
    (d.StandardPricing(), "200.00"),
    (d.ReimbursedPricing(Decimal("0.25")), "150.00"),
    (d.ReimbursedPricing(Decimal("1")), "0.00"),
    (d.LoyaltyPricing(Decimal("5")), "190.00"),
])
def test_policy_changes_amount_without_changing_client_code(batch, policy, expected):
    assert checkout(batch, policy) == Decimal(expected)


def test_new_policy_needs_no_changes_in_sale(batch):
    class FixedPricing:
        def amount_due(self, subtotal):
            return Decimal("1.00")

    assert checkout(batch, FixedPricing()) == Decimal("1.00")


def test_default_policy_is_standard(batch):
    pharmacist = d.Pharmacist("Ф-7", "Бойко Ірина", batch.pharmacy)
    assert isinstance(d.Sale("Ч-1", NOW, d.PaymentMethod.CARD, pharmacist).pricing, d.StandardPricing)


def test_amount_is_rounded_to_cents():
    assert d.ReimbursedPricing(Decimal("0.333")).amount_due(Decimal("10.00")) == Decimal("6.67")


@pytest.mark.parametrize("share, policy_type", [
    (Decimal("0"), d.StandardPricing), (Decimal("0.25"), d.ReimbursedPricing),
])
def test_recipe_chooses_policy(share, policy_type):
    recipe = d.EPrescription("E-1", date(2026, 11, 4), "Paracetamol", 1, d.Doctor("Л", "т"), share)
    assert isinstance(recipe.pricing_policy(), policy_type)
