"""Перевірка того, що схема відкидає некоректні дані (ЛР 7, завдання 1).

Запуск: python check_constraints.py
Код завершення: 0, якщо база відкинула всі некоректні запити.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent.parent / "pharmacy" / "persistence"

BAD_STATEMENTS = {
    "запис-сирота: партія неіснуючої аптеки":
        "INSERT INTO batch (drug_id, series, pharmacy_number, purchase_price_kop, retail_price_kop, quantity) "
        "VALUES (1, 'AM-1', 'А-99', 1, 1, 1)",
    "запис-сирота: резервування неіснуючого покупця":
        "INSERT INTO reservation (code, created_at, expires_at, quantity, state, customer_phone, batch_id) "
        "VALUES ('R-9', '2026-01-01', '2026-01-02', 1, 'Нове', '+380000000000', 1)",
    "видалення препарату, на який посилаються партії":
        "DELETE FROM drug_series WHERE drug_id = 1",
    "дублікат унікального значення: ЄДРПОУ мережі":
        "INSERT INTO pharmacy_chain VALUES (2, 'Інша мережа', '12345678')",
    "дублікат унікального значення: один рецепт у двох продажах":
        "UPDATE sale SET prescription_number = 'E-100' WHERE number IN ('Ч-1', 'Ч-2')",
    "CHECK: кількість резервування 7":
        "UPDATE reservation SET quantity = 7 WHERE code = 'R-5'",
    "CHECK: зарезервовано більше, ніж є в партії":
        "UPDATE batch SET reserved = quantity + 1 WHERE batch_id = 1",
    "CHECK: від'ємний залишок":
        "UPDATE batch SET quantity = -1 WHERE batch_id = 2",
    "CHECK: невідомий стан резервування":
        "UPDATE reservation SET state = 'Загублене' WHERE code = 'R-5'",
    "CHECK: строк дії раніший за створення":
        "UPDATE reservation SET expires_at = '2000-01-01' WHERE code = 'R-5'",
    "CHECK: частка реімбурсації понад 100 %":
        "UPDATE prescription SET reimbursement_bp = 10001 WHERE number = 'E-100'",
    "NOT NULL: препарат без МНН":
        "INSERT INTO drug (trade_name, inn, dosage_form, dosage, manufacturer) "
        "VALUES ('Новий', NULL, 'таблетки', '1 мг', 'Виробник')",
}


def build_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for name in ("schema.sql", "indexes.sql", "seed.sql"):
        connection.executescript((SQL_DIR / name).read_text(encoding="utf-8"))
    return connection


def main() -> int:
    connection = build_database()
    accepted = 0
    for title, statement in BAD_STATEMENTS.items():
        try:
            connection.execute(statement)
        except sqlite3.IntegrityError as error:
            print(f"ВІДКИНУТО  {title}\n           {error}")
        else:
            accepted += 1
            print(f"ПРИЙНЯТО   {title}")
    print(f"Перевірено: {len(BAD_STATEMENTS)}, прийнято некоректних: {accepted}")
    return 1 if accepted else 0


if __name__ == "__main__":
    sys.exit(main())
