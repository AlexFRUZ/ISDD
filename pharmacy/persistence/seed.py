"""Демонстраційні дані для сховища в пам'яті."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from pharmacy.domain import (
    Batch, Doctor, EPrescription, OtcDrug, Pharmacist, Pharmacy, PharmacyChain,
    PrescriptionDrug, PrescriptionState,
)
from pharmacy.persistence.store import MemoryStore


def build_demo_store(today: date, path: str | Path | None = None) -> MemoryStore:
    first = Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    second = Pharmacy("А-02", "вул. Проскурівська, 7", "Хмельницький", "+380382000002", "8:00-22:00")
    store = MemoryStore(PharmacyChain("Мережа аптек", "12345678", [first, second]), path)

    amoxicillin = PrescriptionDrug("Амоксил", "Amoxicillin", "таблетки", "500 мг", "Київмедпрепарат")
    insulin = PrescriptionDrug("Актрапід", "Insulin", "ампули", "100 МО/мл", "Ново Нордіск")
    paracetamol = OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    later, sooner = today + timedelta(days=365), today + timedelta(days=90)
    Batch("AM-1", sooner, Decimal("80"), Decimal("120.00"), 10, amoxicillin, first)
    Batch("AM-2", later, Decimal("85"), Decimal("125.00"), 10, amoxicillin, first)
    Batch("IN-1", later, Decimal("300"), Decimal("400.00"), 5, insulin, second)
    Batch("PA-1", later, Decimal("20"), Decimal("35.50"), 20, paracetamol, first)
    Batch("PA-0", today + timedelta(days=10), Decimal("20"), Decimal("30.00"), 20, paracetamol, first)

    pharmacist = Pharmacist("Ф-7", "Бойко Ірина", first)
    store.pharmacists[pharmacist.personnel_number] = pharmacist

    doctor = Doctor("Коваль Петро", "терапевт")
    recipes = [
        EPrescription("E-100", today, "Amoxicillin", 2, doctor),
        EPrescription("E-101", today, "Amoxicillin", 2, doctor, Decimal("0.25")),
        EPrescription("E-102", today, "Insulin", 1, doctor),
        EPrescription("E-200", today - timedelta(days=31), "Amoxicillin", 1, doctor),
        EPrescription("E-300", today, "Amoxicillin", 1, doctor, state=PrescriptionState.REDEEMED),
        EPrescription("E-301", today, "Amoxicillin", 1, doctor, state=PrescriptionState.CANCELLED),
    ]
    store.prescriptions.update({r.number: r for r in recipes})
    return store
