from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pharmacy.domain import (
    Batch, Customer, Delivery, Director, Doctor, Drug, EPrescription, Manager, OtcDrug, PaymentMethod,
    Pharmacist, Pharmacy, PharmacyChain, PrescriptionDrug, PrescriptionState, Reservation,
    ReservationState, Sale, SaleLine, Supplier, WriteOff, WriteOffReason,
)

SQL_DIR = Path(__file__).parent
CHAIN_ID = 1


def to_kopecks(value: Decimal) -> int:
    return int((value * 100).to_integral_value())


def from_kopecks(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(Decimal("0.01"))


def to_basis_points(share: Decimal) -> int:
    return int((share * 10000).to_integral_value())


def from_basis_points(value: int) -> Decimal:
    return Decimal(value) / 10000


def _stamp(moment: datetime) -> str:
    return moment.isoformat(sep=" ")


class SqliteRepository:
    def __init__(self, uow: SqliteUnitOfWork) -> None:
        self._uow = uow

    @property
    def _identity(self) -> dict:
        return self._uow.identity

    def _one(self, sql: str, *params) -> sqlite3.Row | None:
        return self._uow.connection.execute(sql, params).fetchone()

    def _all(self, sql: str, *params) -> list[sqlite3.Row]:
        return self._uow.connection.execute(sql, params).fetchall()

    def _run(self, sql: str, *params) -> sqlite3.Cursor:
        return self._uow.connection.execute(sql, params)


class SqlitePharmacyRepository(SqliteRepository):
    def get(self, number: str) -> Pharmacy | None:
        if ("pharmacy", number) in self._identity:
            return self._identity[("pharmacy", number)]
        row = self._one("SELECT * FROM pharmacy WHERE number = ?", number)
        return self._load(row) if row else None

    def _load(self, row: sqlite3.Row) -> Pharmacy:
        pharmacy = Pharmacy(row["number"], row["address"], row["city"], row["phone"], row["schedule"])
        self._identity[("pharmacy", pharmacy.number)] = pharmacy
        self._uow.batches.load_for(pharmacy)
        self._uow.pharmacists.load_for(pharmacy)
        self._uow.managers.load_for(pharmacy)
        return pharmacy

    def chain(self) -> PharmacyChain:
        row = self._one("SELECT * FROM pharmacy_chain WHERE chain_id = ?", CHAIN_ID)
        numbers = self._all("SELECT number FROM pharmacy WHERE chain_id = ? ORDER BY number", CHAIN_ID)
        return PharmacyChain(row["name"], row["edrpou"], [self.get(r["number"]) for r in numbers])

    def save_chain(self, chain: PharmacyChain) -> None:
        self._run("""INSERT INTO pharmacy_chain (chain_id, name, edrpou) VALUES (?, ?, ?)
                     ON CONFLICT (chain_id) DO UPDATE SET name = excluded.name, edrpou = excluded.edrpou""",
                  CHAIN_ID, chain.name, chain.edrpou)
        for pharmacy in chain.pharmacies:
            self.save(pharmacy)

    def save(self, pharmacy: Pharmacy) -> None:
        self._run("""INSERT INTO pharmacy (number, chain_id, address, city, phone, schedule)
                     VALUES (?, ?, ?, ?, ?, ?)
                     ON CONFLICT (number) DO UPDATE SET address = excluded.address, city = excluded.city,
                         phone = excluded.phone, schedule = excluded.schedule""",
                  pharmacy.number, CHAIN_ID, pharmacy.address, pharmacy.city, pharmacy.phone, pharmacy.schedule)
        self._identity[("pharmacy", pharmacy.number)] = pharmacy

    def delete(self, number: str) -> None:
        self._run("DELETE FROM pharmacy WHERE number = ?", number)
        self._identity.pop(("pharmacy", number), None)

    def find_by_city(self, city: str) -> list[Pharmacy]:
        rows = self._all("SELECT number FROM pharmacy WHERE city = ? ORDER BY number", city)
        return [self.get(r["number"]) for r in rows]


class SqlitePharmacistRepository(SqliteRepository):
    def load_for(self, pharmacy: Pharmacy) -> None:
        for row in self._all("SELECT * FROM pharmacist WHERE pharmacy_number = ?", pharmacy.number):
            key = ("pharmacist", row["personnel_number"])
            if key not in self._identity:
                self._identity[key] = Pharmacist(row["personnel_number"], row["full_name"], pharmacy)

    def get(self, personnel_number: str) -> Pharmacist | None:
        key = ("pharmacist", personnel_number)
        if key not in self._identity:
            row = self._one("SELECT pharmacy_number FROM pharmacist WHERE personnel_number = ?", personnel_number)
            if row is None:
                return None
            self._uow.pharmacies.get(row["pharmacy_number"])
        return self._identity[key]

    def save(self, pharmacist: Pharmacist) -> None:
        self._run("""INSERT INTO pharmacist (personnel_number, full_name, pharmacy_number) VALUES (?, ?, ?)
                     ON CONFLICT (personnel_number) DO UPDATE SET full_name = excluded.full_name,
                         pharmacy_number = excluded.pharmacy_number""",
                  pharmacist.personnel_number, pharmacist.full_name, pharmacist.pharmacy.number)
        self._identity[("pharmacist", pharmacist.personnel_number)] = pharmacist

    def delete(self, personnel_number: str) -> None:
        self._run("DELETE FROM pharmacist WHERE personnel_number = ?", personnel_number)
        self._identity.pop(("pharmacist", personnel_number), None)

    def find_by_pharmacy(self, pharmacy_number: str) -> list[Pharmacist]:
        rows = self._all("SELECT personnel_number FROM pharmacist WHERE pharmacy_number = ?", pharmacy_number)
        return [self.get(r["personnel_number"]) for r in rows]


class SqliteManagerRepository(SqliteRepository):
    def load_for(self, pharmacy: Pharmacy) -> None:
        for row in self._all("SELECT * FROM manager WHERE pharmacy_number = ?", pharmacy.number):
            key = ("manager", row["personnel_number"])
            if key not in self._identity:
                self._identity[key] = Manager(row["personnel_number"], row["full_name"], pharmacy)

    def get(self, personnel_number: str) -> Manager | None:
        key = ("manager", personnel_number)
        if key not in self._identity:
            row = self._one("SELECT pharmacy_number FROM manager WHERE personnel_number = ?", personnel_number)
            if row is None:
                return None
            self._uow.pharmacies.get(row["pharmacy_number"])
        return self._identity[key]

    def save(self, manager: Manager) -> None:
        self._run("""INSERT INTO manager (personnel_number, full_name, pharmacy_number) VALUES (?, ?, ?)
                     ON CONFLICT (personnel_number) DO UPDATE SET full_name = excluded.full_name,
                         pharmacy_number = excluded.pharmacy_number""",
                  manager.personnel_number, manager.full_name, manager.pharmacy.number)
        self._identity[("manager", manager.personnel_number)] = manager

    def delete(self, personnel_number: str) -> None:
        self._run("DELETE FROM manager WHERE personnel_number = ?", personnel_number)
        self._identity.pop(("manager", personnel_number), None)


class SqliteDirectorRepository(SqliteRepository):
    def get(self, personnel_number: str) -> Director | None:
        key = ("director", personnel_number)
        if key in self._identity:
            return self._identity[key]
        row = self._one("SELECT * FROM director WHERE personnel_number = ?", personnel_number)
        if row is None:
            return None
        self._identity[key] = Director(row["personnel_number"], row["full_name"])
        return self._identity[key]

    def save(self, director: Director) -> None:
        self._run("""INSERT INTO director (personnel_number, full_name) VALUES (?, ?)
                     ON CONFLICT (personnel_number) DO UPDATE SET full_name = excluded.full_name""",
                  director.personnel_number, director.full_name)
        self._identity[("director", director.personnel_number)] = director

    def delete(self, personnel_number: str) -> None:
        self._run("DELETE FROM director WHERE personnel_number = ?", personnel_number)
        self._identity.pop(("director", personnel_number), None)


class SqliteDrugRepository(SqliteRepository):
    SELECT = """SELECT d.*, p.control_group, o.check_limit FROM drug d
                LEFT JOIN prescription_drug p ON p.drug_id = d.drug_id
                LEFT JOIN otc_drug o ON o.drug_id = d.drug_id"""

    def _build(self, row: sqlite3.Row) -> Drug:
        key = ("drug", row["drug_id"])
        if key in self._identity:
            return self._identity[key]
        common = (row["trade_name"], row["inn"], row["dosage_form"], row["dosage"], row["manufacturer"])
        if row["control_group"] is not None:
            drug = PrescriptionDrug(*common, control_group=row["control_group"])
        elif row["check_limit"] is not None:
            drug = OtcDrug(*common, check_limit=row["check_limit"])
        else:
            drug = Drug(*common)
        self._identity[key] = drug
        return drug

    def by_id(self, drug_id: int) -> Drug:
        return self._build(self._one(f"{self.SELECT} WHERE d.drug_id = ?", drug_id))

    def get(self, trade_name: str) -> Drug | None:
        row = self._one(f"{self.SELECT} WHERE d.trade_name = ?", trade_name)
        return self._build(row) if row else None

    def id_of(self, trade_name: str) -> int:
        return self._one("SELECT drug_id FROM drug WHERE trade_name = ?", trade_name)["drug_id"]

    def save(self, drug: Drug) -> None:
        self._run("""INSERT INTO drug (trade_name, inn, dosage_form, dosage, manufacturer) VALUES (?, ?, ?, ?, ?)
                     ON CONFLICT (trade_name) DO UPDATE SET inn = excluded.inn, dosage_form = excluded.dosage_form,
                         dosage = excluded.dosage, manufacturer = excluded.manufacturer""",
                  drug.trade_name, drug.inn, drug.dosage_form, drug.dosage, drug.manufacturer)
        drug_id = self.id_of(drug.trade_name)
        if isinstance(drug, PrescriptionDrug):
            self._run("""INSERT INTO prescription_drug (drug_id, control_group) VALUES (?, ?)
                         ON CONFLICT (drug_id) DO UPDATE SET control_group = excluded.control_group""",
                      drug_id, drug.control_group)
        elif isinstance(drug, OtcDrug):
            self._run("""INSERT INTO otc_drug (drug_id, check_limit) VALUES (?, ?)
                         ON CONFLICT (drug_id) DO UPDATE SET check_limit = excluded.check_limit""",
                      drug_id, drug.check_limit)
        self._identity[("drug", drug_id)] = drug

    def delete(self, trade_name: str) -> None:
        row = self._one("SELECT drug_id FROM drug WHERE trade_name = ?", trade_name)
        if row:
            self._run("DELETE FROM drug WHERE drug_id = ?", row["drug_id"])
            self._identity.pop(("drug", row["drug_id"]), None)

    def find_by_inn(self, inn: str) -> list[Drug]:
        return [self._build(r) for r in self._all(f"{self.SELECT} WHERE d.inn = ? ORDER BY d.trade_name", inn)]


class SqliteBatchRepository(SqliteRepository):
    SELECT = """SELECT b.*, s.expiry_date FROM batch b
                JOIN drug_series s ON s.drug_id = b.drug_id AND s.series = b.series"""

    def load_for(self, pharmacy: Pharmacy) -> None:
        for row in self._all(f"{self.SELECT} WHERE b.pharmacy_number = ?", pharmacy.number):
            if ("batch", row["batch_id"]) not in self._identity:
                self._build(row, pharmacy)

    def _build(self, row: sqlite3.Row, pharmacy: Pharmacy) -> Batch:
        batch = Batch(row["series"], date.fromisoformat(row["expiry_date"]),
                      from_kopecks(row["purchase_price_kop"]), from_kopecks(row["retail_price_kop"]),
                      row["quantity"], self._uow.drugs.by_id(row["drug_id"]), pharmacy, row["reserved"])
        self._identity[("batch", row["batch_id"])] = batch
        return batch

    def by_id(self, batch_id: int) -> Batch:
        key = ("batch", batch_id)
        if key not in self._identity:
            row = self._one("SELECT pharmacy_number FROM batch WHERE batch_id = ?", batch_id)
            self._uow.pharmacies.get(row["pharmacy_number"])
        return self._identity[key]

    def id_of(self, batch: Batch) -> int:
        row = self._one("""SELECT b.batch_id FROM batch b JOIN drug d ON d.drug_id = b.drug_id
                           WHERE b.pharmacy_number = ? AND d.trade_name = ? AND b.series = ?""",
                        batch.pharmacy.number, batch.drug.trade_name, batch.series)
        return row["batch_id"]

    def get(self, key: tuple[str, str, str]) -> Batch | None:
        pharmacy_number, trade_name, series = key
        row = self._one("""SELECT b.batch_id FROM batch b JOIN drug d ON d.drug_id = b.drug_id
                           WHERE b.pharmacy_number = ? AND d.trade_name = ? AND b.series = ?""",
                        pharmacy_number, trade_name, series)
        return self.by_id(row["batch_id"]) if row else None

    def save(self, batch: Batch) -> None:
        drug_id = self._uow.drugs.id_of(batch.drug.trade_name)
        self._run("""INSERT INTO drug_series (drug_id, series, expiry_date) VALUES (?, ?, ?)
                     ON CONFLICT (drug_id, series) DO UPDATE SET expiry_date = excluded.expiry_date""",
                  drug_id, batch.series, batch.expiry_date.isoformat())
        self._run("""INSERT INTO batch (drug_id, series, pharmacy_number, purchase_price_kop, retail_price_kop,
                                        quantity, reserved) VALUES (?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (drug_id, series, pharmacy_number) DO UPDATE SET
                         purchase_price_kop = excluded.purchase_price_kop,
                         retail_price_kop = excluded.retail_price_kop,
                         quantity = excluded.quantity, reserved = excluded.reserved""",
                  drug_id, batch.series, batch.pharmacy.number, to_kopecks(batch.purchase_price),
                  to_kopecks(batch.retail_price), batch.quantity, batch.reserved)
        self._identity[("batch", self.id_of(batch))] = batch

    def delete(self, key: tuple[str, str, str]) -> None:
        batch = self.get(key)
        if batch is not None:
            batch_id = self.id_of(batch)
            self._run("DELETE FROM batch WHERE batch_id = ?", batch_id)
            self._identity.pop(("batch", batch_id), None)
            batch.pharmacy.batches.remove(batch)

    def find_expiring(self, until: date) -> list[Batch]:
        rows = self._all(f"{self.SELECT} WHERE s.expiry_date <= ? ORDER BY s.expiry_date", until.isoformat())
        return [self.by_id(r["batch_id"]) for r in rows]

    def expiry_of_series(self, trade_name: str, series: str) -> date | None:
        row = self._one("""SELECT s.expiry_date FROM drug_series s JOIN drug d ON d.drug_id = s.drug_id
                           WHERE d.trade_name = ? AND s.series = ?""", trade_name, series)
        return date.fromisoformat(row["expiry_date"]) if row else None


class SqliteSupplierRepository(SqliteRepository):
    def get(self, name: str) -> Supplier | None:
        key = ("supplier", name)
        if key in self._identity:
            return self._identity[key]
        row = self._one("SELECT * FROM supplier WHERE name = ?", name)
        if row is None:
            return None
        self._identity[key] = Supplier(row["name"], row["phone"])
        return self._identity[key]

    def id_of(self, name: str) -> int:
        return self._one("SELECT supplier_id FROM supplier WHERE name = ?", name)["supplier_id"]

    def save(self, supplier: Supplier) -> None:
        self._run("""INSERT INTO supplier (name, phone) VALUES (?, ?)
                     ON CONFLICT (name) DO UPDATE SET phone = excluded.phone""", supplier.name, supplier.phone)
        self._identity[("supplier", supplier.name)] = supplier

    def delete(self, name: str) -> None:
        self._run("DELETE FROM supplier WHERE name = ?", name)
        self._identity.pop(("supplier", name), None)


class SqliteDeliveryRepository(SqliteRepository):
    def get(self, invoice_number: str) -> Delivery | None:
        key = ("delivery", invoice_number)
        if key in self._identity:
            return self._identity[key]
        row = self._one("""SELECT d.*, s.name AS supplier_name FROM delivery d
                           JOIN supplier s ON s.supplier_id = d.supplier_id WHERE d.invoice_number = ?""",
                        invoice_number)
        if row is None:
            return None
        batches = [self._uow.batches.by_id(r["batch_id"]) for r in self._all(
            "SELECT batch_id FROM batch WHERE invoice_number = ? ORDER BY batch_id", invoice_number)]
        delivery = Delivery(row["invoice_number"], date.fromisoformat(row["delivery_date"]),
                            self._uow.suppliers.get(row["supplier_name"]), batches)
        self._identity[key] = delivery
        return delivery

    def save(self, delivery: Delivery) -> None:
        self._uow.suppliers.save(delivery.supplier)
        self._run("""INSERT INTO delivery (invoice_number, delivery_date, supplier_id) VALUES (?, ?, ?)
                     ON CONFLICT (invoice_number) DO UPDATE SET delivery_date = excluded.delivery_date""",
                  delivery.invoice_number, delivery.delivery_date.isoformat(),
                  self._uow.suppliers.id_of(delivery.supplier.name))
        for batch in delivery.batches:
            self._uow.batches.save(batch)
            self._run("UPDATE batch SET invoice_number = ? WHERE batch_id = ?",
                      delivery.invoice_number, self._uow.batches.id_of(batch))
        self._identity[("delivery", delivery.invoice_number)] = delivery

    def delete(self, invoice_number: str) -> None:
        self._run("UPDATE batch SET invoice_number = NULL WHERE invoice_number = ?", invoice_number)
        self._run("DELETE FROM delivery WHERE invoice_number = ?", invoice_number)
        self._identity.pop(("delivery", invoice_number), None)


class SqliteWriteOffRepository(SqliteRepository):
    def get(self, number: str) -> WriteOff | None:
        key = ("write_off", number)
        if key in self._identity:
            return self._identity[key]
        row = self._one("SELECT * FROM write_off WHERE number = ?", number)
        if row is None:
            return None
        manager = self._uow.managers.get(row["personnel_number"])
        write_off = WriteOff(row["number"], datetime.fromisoformat(row["written_at"]), row["quantity"],
                             WriteOffReason(row["reason"]), self._uow.batches.by_id(row["batch_id"]), manager)
        self._identity[key] = write_off
        return write_off

    def save(self, write_off: WriteOff) -> None:
        self._run("""INSERT INTO write_off (number, written_at, quantity, reason, batch_id, personnel_number)
                     VALUES (?, ?, ?, ?, ?, ?)
                     ON CONFLICT (number) DO UPDATE SET reason = excluded.reason""",
                  write_off.number, _stamp(write_off.written_at), write_off.quantity, write_off.reason.value,
                  self._uow.batches.id_of(write_off.batch), write_off.manager.personnel_number)
        self._identity[("write_off", write_off.number)] = write_off

    def delete(self, number: str) -> None:
        self._run("DELETE FROM write_off WHERE number = ?", number)
        self._identity.pop(("write_off", number), None)

    def find_by_pharmacy(self, pharmacy_number: str) -> list[WriteOff]:
        rows = self._all("""SELECT w.number FROM write_off w JOIN batch b ON b.batch_id = w.batch_id
                            WHERE b.pharmacy_number = ? ORDER BY w.written_at, w.number""", pharmacy_number)
        return [self.get(r["number"]) for r in rows]


class SqliteCustomerRepository(SqliteRepository):
    def get(self, phone: str) -> Customer | None:
        key = ("customer", phone)
        if key in self._identity:
            return self._identity[key]
        row = self._one("SELECT * FROM customer WHERE phone = ?", phone)
        if row is None:
            return None
        customer = Customer(row["phone"], row["full_name"])
        self._identity[key] = customer
        self._uow.reservations.load_for(customer)
        return customer

    def save(self, customer: Customer) -> None:
        self._run("""INSERT INTO customer (phone, full_name) VALUES (?, ?)
                     ON CONFLICT (phone) DO UPDATE SET full_name = excluded.full_name""",
                  customer.phone, customer.full_name)
        self._identity[("customer", customer.phone)] = customer

    def delete(self, phone: str) -> None:
        self._run("DELETE FROM customer WHERE phone = ?", phone)
        self._identity.pop(("customer", phone), None)


class SqliteReservationRepository(SqliteRepository):
    def load_for(self, customer: Customer) -> None:
        for row in self._all("SELECT * FROM reservation WHERE customer_phone = ?", customer.phone):
            if ("reservation", row["code"]) not in self._identity:
                self._build(row, customer)

    def _build(self, row: sqlite3.Row, customer: Customer) -> Reservation:
        number = row["prescription_number"]
        reservation = Reservation.restore(
            code=row["code"], created_at=datetime.fromisoformat(row["created_at"]),
            quantity=row["quantity"], customer=customer, batch=self._uow.batches.by_id(row["batch_id"]),
            prescription=self._uow.prescriptions.get(number) if number else None,
            expires_at=datetime.fromisoformat(row["expires_at"]), extensions=row["extensions"],
            state=ReservationState(row["state"]), customer_notified=bool(row["customer_notified"]),
        )
        self._identity[("reservation", reservation.code)] = reservation
        return reservation

    def get(self, code: str) -> Reservation | None:
        key = ("reservation", code)
        if key not in self._identity:
            row = self._one("SELECT customer_phone FROM reservation WHERE code = ?", code)
            if row is None:
                return None
            self._uow.customers.get(row["customer_phone"])
        return self._identity[key]

    def save(self, reservation: Reservation) -> None:
        recipe = reservation.prescription
        self._run("""INSERT INTO reservation (code, created_at, expires_at, quantity, extensions, state,
                                              customer_notified, customer_phone, batch_id, prescription_number)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (code) DO UPDATE SET expires_at = excluded.expires_at,
                         extensions = excluded.extensions, state = excluded.state,
                         customer_notified = excluded.customer_notified""",
                  reservation.code, _stamp(reservation.created_at), _stamp(reservation.expires_at),
                  reservation.quantity, reservation.extensions, reservation.state.value,
                  int(reservation.customer_notified), reservation.customer.phone,
                  self._uow.batches.id_of(reservation.batch), recipe.number if recipe else None)
        self._identity[("reservation", reservation.code)] = reservation

    def delete(self, code: str) -> None:
        reservation = self.get(code)
        if reservation is not None:
            self._run("DELETE FROM reservation WHERE code = ?", code)
            self._identity.pop(("reservation", code), None)
            reservation.customer.reservations.remove(reservation)

    def find_active_by_customer(self, phone: str) -> list[Reservation]:
        customer = self._uow.customers.get(phone)
        return customer.active_reservations if customer else []

    def find_overdue(self, moment: datetime) -> list[Reservation]:
        rows = self._all("""SELECT code FROM reservation
                            WHERE state IN ('Підтверджене', 'Готове', 'Продовжене') AND expires_at < ?""",
                         _stamp(moment))
        return [self.get(r["code"]) for r in rows]


class SqlitePrescriptionRepository(SqliteRepository):
    def _doctor(self, doctor_id: int) -> Doctor:
        key = ("doctor", doctor_id)
        if key not in self._identity:
            row = self._one("SELECT * FROM doctor WHERE doctor_id = ?", doctor_id)
            self._identity[key] = Doctor(row["full_name"], row["specialty"])
        return self._identity[key]

    def get(self, number: str) -> EPrescription | None:
        key = ("prescription", number)
        if key in self._identity:
            return self._identity[key]
        row = self._one("SELECT * FROM prescription WHERE number = ?", number)
        if row is None:
            return None
        recipe = EPrescription(row["number"], date.fromisoformat(row["issued_on"]), row["inn"],
                               row["prescribed_quantity"], self._doctor(row["doctor_id"]),
                               from_basis_points(row["reimbursement_bp"]), PrescriptionState(row["state"]))
        self._identity[key] = recipe
        return recipe

    def _save_doctor(self, doctor: Doctor) -> int:
        self._run("INSERT INTO doctor (full_name, specialty) VALUES (?, ?) ON CONFLICT DO NOTHING",
                  doctor.full_name, doctor.specialty)
        return self._one("SELECT doctor_id FROM doctor WHERE full_name = ? AND specialty = ?",
                         doctor.full_name, doctor.specialty)["doctor_id"]

    def save(self, recipe: EPrescription) -> None:
        doctor_id = self._save_doctor(recipe.doctor)
        self._run("""INSERT INTO prescription (number, issued_on, inn, prescribed_quantity, reimbursement_bp,
                                               state, doctor_id) VALUES (?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (number) DO UPDATE SET state = excluded.state""",
                  recipe.number, recipe.issued_on.isoformat(), recipe.inn, recipe.prescribed_quantity,
                  to_basis_points(recipe.reimbursement_share), recipe.state.value, doctor_id)
        self._identity[("prescription", recipe.number)] = recipe

    def delete(self, number: str) -> None:
        self._run("DELETE FROM prescription WHERE number = ?", number)
        self._identity.pop(("prescription", number), None)

    def find_by_state(self, state: PrescriptionState) -> list[EPrescription]:
        rows = self._all("SELECT number FROM prescription WHERE state = ? ORDER BY number", state.value)
        return [self.get(r["number"]) for r in rows]


class SqliteSaleRepository(SqliteRepository):
    def get(self, number: str) -> Sale | None:
        key = ("sale", number)
        if key in self._identity:
            return self._identity[key]
        row = self._one("SELECT * FROM sale WHERE number = ?", number)
        return self._build(row) if row else None

    def _build(self, row: sqlite3.Row) -> Sale:
        phone, recipe_number = row["customer_phone"], row["prescription_number"]
        recipe = self._uow.prescriptions.get(recipe_number) if recipe_number else None
        sale = Sale(row["number"], datetime.fromisoformat(row["sold_at"]), PaymentMethod(row["payment_method"]),
                    self._uow.pharmacists.get(row["personnel_number"]),
                    self._uow.customers.get(phone) if phone else None, recipe,
                    from_kopecks(row["total_kop"]))
        if recipe is not None:
            sale.pricing = recipe.pricing_policy()
        for line in self._all("SELECT * FROM sale_line WHERE sale_number = ?", sale.number):
            sale.lines.append(SaleLine(line["quantity"], from_kopecks(line["unit_price_kop"]), sale,
                                       self._uow.batches.by_id(line["batch_id"])))
        self._identity[("sale", sale.number)] = sale
        return sale

    def save(self, sale: Sale) -> None:
        recipe, customer = sale.prescription, sale.customer
        self._run("""INSERT INTO sale (number, sold_at, payment_method, total_kop, personnel_number,
                                       customer_phone, prescription_number) VALUES (?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (number) DO UPDATE SET total_kop = excluded.total_kop""",
                  sale.number, _stamp(sale.sold_at), sale.payment_method.value, to_kopecks(sale.total),
                  sale.pharmacist.personnel_number, customer.phone if customer else None,
                  recipe.number if recipe else None)
        self._run("DELETE FROM sale_line WHERE sale_number = ?", sale.number)
        for line in sale.lines:
            self._run("INSERT INTO sale_line (sale_number, batch_id, quantity, unit_price_kop) VALUES (?, ?, ?, ?)",
                      sale.number, self._uow.batches.id_of(line.batch), line.quantity, to_kopecks(line.unit_price))
        self._identity[("sale", sale.number)] = sale

    def delete(self, number: str) -> None:
        self._run("DELETE FROM sale WHERE number = ?", number)
        self._identity.pop(("sale", number), None)

    def find_by_period(self, start: datetime, end: datetime) -> list[Sale]:
        rows = self._all("SELECT number FROM sale WHERE sold_at BETWEEN ? AND ? ORDER BY sold_at",
                         _stamp(start), _stamp(end))
        return [self.get(r["number"]) for r in rows]


class SqliteUnitOfWork:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        connection.row_factory = sqlite3.Row
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys = ON")
        self.identity: dict = {}
        self.pharmacies = SqlitePharmacyRepository(self)
        self.pharmacists = SqlitePharmacistRepository(self)
        self.drugs = SqliteDrugRepository(self)
        self.batches = SqliteBatchRepository(self)
        self.customers = SqliteCustomerRepository(self)
        self.reservations = SqliteReservationRepository(self)
        self.prescriptions = SqlitePrescriptionRepository(self)
        self.sales = SqliteSaleRepository(self)
        self.managers = SqliteManagerRepository(self)
        self.directors = SqliteDirectorRepository(self)
        self.suppliers = SqliteSupplierRepository(self)
        self.deliveries = SqliteDeliveryRepository(self)
        self.write_offs = SqliteWriteOffRepository(self)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.clear()
        self.connection.execute("BEGIN")
        try:
            yield
        except BaseException:
            self.connection.execute("ROLLBACK")
            self.clear()
            raise
        self.connection.execute("COMMIT")

    def next_number(self, kind: str) -> int:
        self.connection.execute("""INSERT INTO sequence (kind, value) VALUES (?, 1)
                                   ON CONFLICT (kind) DO UPDATE SET value = value + 1""", (kind,))
        return self.connection.execute("SELECT value FROM sequence WHERE kind = ?", (kind,)).fetchone()["value"]

    def clear(self) -> None:
        self.identity.clear()

    def close(self) -> None:
        self.connection.close()


def create_schema(connection: sqlite3.Connection) -> None:
    for name in ("schema.sql", "indexes.sql"):
        connection.executescript((SQL_DIR / name).read_text(encoding="utf-8"))


def create_database(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    create_schema(connection)
    connection.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
    connection.close()


def open_database(path: str | Path) -> SqliteUnitOfWork:
    return SqliteUnitOfWork(sqlite3.connect(path))
