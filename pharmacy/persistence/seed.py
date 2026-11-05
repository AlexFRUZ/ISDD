from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pharmacy.domain import (
    Batch, Director, Doctor, EPrescription, Manager, OtcDrug, Pharmacist, Pharmacy, PharmacyChain,
    PrescriptionDrug, PrescriptionState, Supplier,
)
from pharmacy.persistence.repositories import UnitOfWork


def populate(uow: UnitOfWork, today: date) -> None:
    first = Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    second = Pharmacy("А-02", "вул. Проскурівська, 7", "Хмельницький", "+380382000002", "8:00-22:00")
    uow.pharmacies.save_chain(PharmacyChain("Мережа аптек", "12345678", [first, second]))

    amoxicillin = PrescriptionDrug("Амоксил", "Amoxicillin", "таблетки", "500 мг", "Київмедпрепарат", control_group="антибіотики")
    insulin = PrescriptionDrug("Актрапід", "Insulin", "ампули", "100 МО/мл", "Ново Нордіск", control_group="інсуліни")
    paracetamol = OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    for drug in (amoxicillin, insulin, paracetamol):
        uow.drugs.save(drug)

    later, sooner = today + timedelta(days=365), today + timedelta(days=90)
    batches = [
        Batch("AM-1", sooner, Decimal("80"), Decimal("120.00"), 10, amoxicillin, first),
        Batch("AM-2", later, Decimal("85"), Decimal("125.00"), 10, amoxicillin, first),
        Batch("IN-1", later, Decimal("300"), Decimal("400.00"), 5, insulin, second),
        Batch("PA-1", later, Decimal("20"), Decimal("35.50"), 20, paracetamol, first),
        Batch("PA-0", today + timedelta(days=10), Decimal("20"), Decimal("30.00"), 20, paracetamol, first),
    ]
    for batch in batches:
        uow.batches.save(batch)

    uow.pharmacists.save(Pharmacist("Ф-7", "Бойко Ірина", first))
    uow.managers.save(Manager("З-1", "Данилюк Тетяна", first))
    uow.managers.save(Manager("З-2", "Приходько Максим", second))
    uow.directors.save(Director("Д-1", "Лановий Сергій"))
    uow.suppliers.save(Supplier("Оптима-Фарм", "+380441110001"))

    doctor = Doctor("Коваль Петро", "терапевт")
    recipes = [
        EPrescription("E-100", today, "Amoxicillin", 2, doctor),
        EPrescription("E-101", today, "Amoxicillin", 2, doctor, Decimal("0.25")),
        EPrescription("E-102", today, "Insulin", 1, doctor),
        EPrescription("E-200", today - timedelta(days=31), "Amoxicillin", 1, doctor),
        EPrescription("E-300", today, "Amoxicillin", 1, doctor, state=PrescriptionState.REDEEMED),
        EPrescription("E-301", today, "Amoxicillin", 1, doctor, state=PrescriptionState.CANCELLED),
    ]
    for recipe in recipes:
        uow.prescriptions.save(recipe)
