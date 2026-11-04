"""Тести репозиторіїв. Фікстура uow виконує кожен тест для обох реалізацій (ЛР 7)."""
import dataclasses
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

import pytest

import pharmacy.domain as d
from conftest import NOW, TODAY, make_sqlite_uow
from pharmacy.persistence.seed import populate

SCALARS = (str, int, Decimal, date, Enum, type(None))


def scalars(entity):
    """Значення всіх скалярних полів: доменні об'єкти порівнюються за ідентичністю."""
    values = {f.name: getattr(entity, f.name) for f in dataclasses.fields(entity)}
    return {name: value for name, value in values.items() if isinstance(value, SCALARS)}


def reread(uow, repository, key):
    uow.clear()
    return repository.get(key)


@pytest.fixture
def world(uow):
    populate(uow, TODAY)
    return uow


def first_pharmacy(uow):
    return uow.pharmacies.get("А-01")


def batch_of(uow):
    return uow.batches.get(("А-01", "Парацетамол", "PA-1"))


def new_reservation(uow, code="R-1", phone="+380671112233"):
    customer = uow.customers.get(phone) or d.Customer(phone, "Іваненко Марія")
    uow.customers.save(customer)
    batch = batch_of(uow)
    reservation = customer.create_reservation(code, NOW, 2, batch)
    reservation.confirm()
    uow.batches.save(batch)
    uow.reservations.save(reservation)
    return reservation


def new_sale(uow, number="Ч-1"):
    batch = batch_of(uow)
    pharmacist = uow.pharmacists.get("Ф-7")
    sale = d.Sale(number, NOW, d.PaymentMethod.CARD, pharmacist)
    sale.add_line(batch, 2)
    sale.complete()
    uow.batches.save(batch)
    uow.sales.save(sale)
    return sale


# --- Збереження і читання дають рівний об'єкт --------------------------------------

def test_round_trip_pharmacy(world):
    original = scalars(first_pharmacy(world))
    assert scalars(reread(world, world.pharmacies, "А-01")) == original


def test_round_trip_chain(world):
    world.clear()
    chain = world.pharmacies.chain()
    assert (chain.name, chain.edrpou) == ("Мережа аптек", "12345678")
    assert [p.number for p in chain.pharmacies] == ["А-01", "А-02"]


def test_round_trip_pharmacist(world):
    loaded = reread(world, world.pharmacists, "Ф-7")
    assert scalars(loaded) == {"personnel_number": "Ф-7", "full_name": "Бойко Ірина"}
    assert loaded.pharmacy.number == "А-01"


@pytest.mark.parametrize("name, expected_type", [("Амоксил", d.PrescriptionDrug), ("Парацетамол", d.OtcDrug)])
def test_round_trip_drug_keeps_subclass(world, name, expected_type):
    original = scalars(world.drugs.get(name))
    loaded = reread(world, world.drugs, name)
    assert isinstance(loaded, expected_type) and scalars(loaded) == original


def test_round_trip_batch(world):
    original = scalars(batch_of(world))
    key = ("А-01", "Парацетамол", "PA-1")
    assert scalars(reread(world, world.batches, key)) == original


def test_round_trip_customer(world):
    world.customers.save(d.Customer("+380671112233", "Іваненко Марія"))
    loaded = reread(world, world.customers, "+380671112233")
    assert scalars(loaded) == {"phone": "+380671112233", "full_name": "Іваненко Марія"}


def test_round_trip_prescription(world):
    original = scalars(world.prescriptions.get("E-101"))
    assert scalars(reread(world, world.prescriptions, "E-101")) == original
    assert original["reimbursement_share"] == Decimal("0.25")


def test_round_trip_reservation(world):
    original = scalars(new_reservation(world))
    loaded = reread(world, world.reservations, "R-1")
    assert scalars(loaded) == original
    assert loaded.customer.phone == "+380671112233" and loaded.batch.series == "PA-1"


def test_round_trip_reservation_restores_stock_block(world):
    new_reservation(world)
    world.clear()
    assert batch_of(world).available == 18


def test_round_trip_sale_with_lines(world):
    original = scalars(new_sale(world))
    loaded = reread(world, world.sales, "Ч-1")
    assert scalars(loaded) == original
    assert [(line.quantity, line.unit_price, line.batch.series) for line in loaded.lines] == \
        [(2, Decimal("35.50"), "PA-1")]


def test_saving_again_updates_instead_of_duplicating(world):
    reservation = new_reservation(world)
    reservation.cancel()
    world.batches.save(reservation.batch)
    world.reservations.save(reservation)
    assert reread(world, world.reservations, "R-1").state is d.ReservationState.CANCELLED


# --- Читання неіснуючого об'єкта ---------------------------------------------------

@pytest.mark.parametrize("repository, key", [
    ("pharmacies", "А-99"), ("pharmacists", "Ф-99"), ("drugs", "Невідомий"), ("customers", "+380"),
    ("reservations", "R-99"), ("prescriptions", "E-999"), ("sales", "Ч-99"),
    ("batches", ("А-01", "Парацетамол", "NO")),
])
def test_missing_object_is_none(world, repository, key):
    assert getattr(world, repository).get(key) is None


# --- Пошук за критерієм ------------------------------------------------------------

def test_find_pharmacies_by_city(world):
    assert [p.number for p in world.pharmacies.find_by_city("Хмельницький")] == ["А-01", "А-02"]
    assert world.pharmacies.find_by_city("Львів") == []


def test_find_pharmacists_by_pharmacy(world):
    assert [p.personnel_number for p in world.pharmacists.find_by_pharmacy("А-01")] == ["Ф-7"]


def test_find_drugs_by_inn(world):
    assert [x.trade_name for x in world.drugs.find_by_inn("Insulin")] == ["Актрапід"]


def test_find_expiring_batches_sorted_by_date(world):
    found = world.batches.find_expiring(TODAY + timedelta(days=100))
    assert [b.series for b in found] == ["PA-0", "AM-1"]


def test_find_active_reservations(world):
    new_reservation(world)
    assert [r.code for r in world.reservations.find_active_by_customer("+380671112233")] == ["R-1"]
    assert world.reservations.find_active_by_customer("+380000000000") == []


def test_find_prescriptions_by_state(world):
    found = world.prescriptions.find_by_state(d.PrescriptionState.REDEEMED)
    assert [p.number for p in found] == ["E-300"]


def test_find_sales_by_period(world):
    new_sale(world)
    assert [s.number for s in world.sales.find_by_period(NOW - timedelta(hours=1), NOW + timedelta(hours=1))] == ["Ч-1"]
    assert world.sales.find_by_period(NOW + timedelta(hours=1), NOW + timedelta(hours=2)) == []


# --- Видалення ---------------------------------------------------------------------

@pytest.mark.parametrize("repository, key", [
    ("prescriptions", "E-301"), ("batches", ("А-02", "Актрапід", "IN-1")),
])
def test_delete(world, repository, key):
    target = getattr(world, repository)
    target.delete(key)
    assert reread(world, target, key) is None


def test_delete_pharmacy_without_dependants(world):
    world.pharmacies.save(d.Pharmacy("А-09", "вул. Нова, 1", "Львів", "+380320000009", "9:00-18:00"))
    world.pharmacies.delete("А-09")
    assert reread(world, world.pharmacies, "А-09") is None


def test_saving_again_updates_drug_and_pharmacist(world):
    drug = world.drugs.get("Парацетамол")
    drug.manufacturer = "Фармак"
    world.drugs.save(drug)
    assert reread(world, world.drugs, "Парацетамол").manufacturer == "Фармак"


def test_plain_drug_without_subclass_row_is_restored(world):
    world.drugs.save(d.Drug("Пластир", "Plaster", "пластир", "1 шт", "Виробник"))
    assert type(reread(world, world.drugs, "Пластир")) is d.Drug


def test_delete_drug_without_batches(world):
    world.drugs.save(d.OtcDrug("Вітамін C", "Ascorbic acid", "таблетки", "500 мг", "Дарниця"))
    world.drugs.delete("Вітамін C")
    assert reread(world, world.drugs, "Вітамін C") is None


def test_delete_customer_and_pharmacist_and_pharmacy(world):
    world.customers.save(d.Customer("+380671112233", ""))
    world.customers.delete("+380671112233")
    world.pharmacists.delete("Ф-7")
    assert reread(world, world.customers, "+380671112233") is None
    assert reread(world, world.pharmacists, "Ф-7") is None


def test_delete_reservation_and_sale(world):
    new_reservation(world)
    new_sale(world)
    world.reservations.delete("R-1")
    world.sales.delete("Ч-1")
    assert reread(world, world.reservations, "R-1") is None
    assert reread(world, world.sales, "Ч-1") is None


def test_delete_missing_object_is_harmless(world):
    world.reservations.delete("R-99")
    world.batches.delete(("А-99", "Х", "Y"))
    world.drugs.delete("Невідомий")


# --- Транзакції --------------------------------------------------------------------

def test_transaction_commits_together(world):
    with world.transaction():
        new_reservation(world)
    assert reread(world, world.reservations, "R-1") is not None


def test_transaction_rolls_back_new_object(world):
    with pytest.raises(RuntimeError), world.transaction():
        new_reservation(world)
        raise RuntimeError("збій")
    assert reread(world, world.reservations, "R-1") is None
    assert reread(world, world.customers, "+380671112233") is None
    assert batch_of(world).available == 20


def test_transaction_rolls_back_change_of_existing_object(world):
    with pytest.raises(RuntimeError), world.transaction():
        batch = batch_of(world)
        batch.write_off_sold(5, TODAY)
        world.batches.save(batch)
        raise RuntimeError("збій")
    world.clear()
    assert batch_of(world).quantity == 20


def test_next_number_grows_and_rolls_back(world):
    assert (world.next_number("sale"), world.next_number("sale")) == (1, 2)
    with pytest.raises(RuntimeError), world.transaction():
        world.next_number("sale")
        raise RuntimeError("збій")
    assert world.next_number("sale") == 3


@pytest.mark.req("R6", "R6.4")
def test_use_case_failure_after_redeem_rolls_everything_back(ctx, monkeypatch):
    """UC7 змінює рецепт, партію й продаж: збій на останньому кроці скасовує все."""
    def broken_save(_sale):
        raise RuntimeError("збій запису продажу")

    monkeypatch.setattr(ctx.uow.sales, "save", broken_save)
    with pytest.raises(RuntimeError):
        ctx.sales.sell("Ф-7", "E-100", 1)
    monkeypatch.undo()

    assert ctx.recipe("E-100").state is d.PrescriptionState.ACTIVE
    assert ctx.batch("AM-1").quantity == 10
    assert ctx.uow.next_number("sale") == 1


@pytest.mark.req("R2", "R2.3")
def test_reservation_failure_rolls_everything_back(ctx, monkeypatch):
    def broken_save(_reservation):
        raise RuntimeError("збій запису резервування")

    monkeypatch.setattr(ctx.uow.reservations, "save", broken_save)
    with pytest.raises(RuntimeError):
        ctx.reservations.reserve("+380671112233", "А-01", "Парацетамол", 2)
    monkeypatch.undo()

    assert ctx.batch("PA-1").available == 20
    ctx.uow.clear()
    assert ctx.uow.customers.get("+380671112233") is None


# --- Лише SQLite: обмеження бази даних і перетворення типів --------------------------
# У пам'яті обмежень бази немає: там некоректні дані відкидають інваріанти доменних класів.

@pytest.fixture
def db():
    uow = make_sqlite_uow()
    populate(uow, TODAY)
    yield uow
    uow.close()


def test_sqlite_rejects_orphan(db):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.connection.execute("INSERT INTO pharmacist VALUES ('Ф-1', 'Ім''я', 'А-99')")


def test_sqlite_rejects_duplicate_unique_value(db):
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        db.connection.execute("INSERT INTO pharmacy_chain VALUES (2, 'Інша', '12345678')")


@pytest.mark.parametrize("statement", [
    "UPDATE batch SET reserved = quantity + 1",
    "UPDATE batch SET quantity = -1",
    "UPDATE prescription SET state = 'невідомий'",
    "UPDATE prescription SET reimbursement_bp = 10001",
])
def test_sqlite_rejects_check_violation(db, statement):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.connection.execute(statement)


def test_sqlite_foreign_keys_are_enabled(db):
    assert db.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_sqlite_identity_map_returns_one_object_per_row(db):
    db.clear()
    assert batch_of(db) is batch_of(db)
    assert batch_of(db).pharmacy is db.pharmacies.get("А-01")


def test_sqlite_money_has_no_rounding_errors(db):
    db.clear()
    assert batch_of(db).retail_price == Decimal("35.50")
    stored = db.connection.execute("SELECT retail_price_kop FROM batch WHERE series = 'PA-1'").fetchone()[0]
    assert stored == 3550


def test_sqlite_old_reservation_loads_despite_short_shelf_life(db):
    """Умови створення не перевіряються повторно під час читання давніх записів."""
    new_reservation(db)
    db.connection.execute("UPDATE drug_series SET expiry_date = ? WHERE series = 'PA-1'",
                          ((TODAY + timedelta(days=1)).isoformat(),))
    assert reread(db, db.reservations, "R-1").batch.expiry_date == TODAY + timedelta(days=1)


def test_sqlite_series_keeps_single_expiry_date_for_two_pharmacies(db):
    """Наслідок 3НФ: строк придатності серії зберігається в одному місці."""
    drug = db.drugs.get("Парацетамол")
    second = db.pharmacies.get("А-02")
    db.batches.save(d.Batch("PA-1", date(2027, 11, 4), Decimal("20"), Decimal("36"), 3, drug, second))
    rows = db.connection.execute("SELECT count(*) FROM drug_series WHERE series = 'PA-1'").fetchone()[0]
    assert rows == 1


def test_restored_sale_keeps_reimbursement_policy(ctx):
    result = ctx.sales.sell("Ф-7", "E-101", 2)
    ctx.uow.clear()
    sale = ctx.uow.sales.get(result.number)
    assert sale.total == Decimal("180.00") and sale.pricing.amount_due(sale.subtotal) == sale.total


def test_datetime_survives_round_trip(world):
    new_reservation(world)
    assert reread(world, world.reservations, "R-1").created_at == datetime(2026, 11, 4, 10, 0)
