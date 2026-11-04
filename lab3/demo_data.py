"""Демонстраційні дані прототипу UC7 (зберігаються в пам'яті)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from prescription_sale import InMemoryRegistry, PrescriptionSaleService

from domain import (
    Batch, Doctor, EPrescription, OtcDrug, Pharmacist, Pharmacy, PharmacyChain,
    PrescriptionDrug, PrescriptionState,
)


@dataclass
class World:
    chain: PharmacyChain
    registry: InMemoryRegistry
    service: PrescriptionSaleService
    first: Pharmacy
    second: Pharmacy
    amoxicillin_batch: Batch


def build_world(today: date) -> World:
    first = Pharmacy("А-01", "вул. Подільська, 1", "Хмельницький", "+380382000001", "8:00-20:00")
    second = Pharmacy("А-02", "вул. Проскурівська, 7", "Хмельницький", "+380382000002", "8:00-22:00")
    chain = PharmacyChain("Мережа аптек", "12345678", [first, second])

    amoxicillin = PrescriptionDrug("Амоксил", "Amoxicillin", "таблетки", "500 мг", "Київмедпрепарат")
    insulin = PrescriptionDrug("Актрапід", "Insulin", "ампули", "100 МО/мл", "Ново Нордіск")
    OtcDrug("Парацетамол", "Paracetamol", "таблетки", "500 мг", "Дарниця")
    later = today + timedelta(days=365)
    sooner = today + timedelta(days=90)
    batch = Batch("AM-1", sooner, Decimal("80"), Decimal("120.00"), 10, amoxicillin, first)
    Batch("AM-2", later, Decimal("85"), Decimal("125.00"), 10, amoxicillin, first)
    Batch("IN-1", later, Decimal("300"), Decimal("400.00"), 5, insulin, second)

    doctor = Doctor("Коваль Петро", "терапевт")
    recipes = [
        EPrescription("E-100", today, "Amoxicillin", 2, doctor),
        EPrescription("E-101", today, "Amoxicillin", 2, doctor, Decimal("0.25")),
        EPrescription("E-102", today, "Insulin", 1, doctor),
        EPrescription("E-200", today - timedelta(days=31), "Amoxicillin", 1, doctor),
        EPrescription("E-300", today, "Amoxicillin", 1, doctor, state=PrescriptionState.REDEEMED),
        EPrescription("E-301", today, "Amoxicillin", 1, doctor, state=PrescriptionState.CANCELLED),
    ]
    registry = InMemoryRegistry(recipes)
    pharmacist = Pharmacist("Ф-7", "Бойко Ірина", first)
    service = PrescriptionSaleService(chain, registry, pharmacist)
    return World(chain, registry, service, first, second, batch)
