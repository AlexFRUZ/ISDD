from __future__ import annotations

import sqlite3
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pharmacy.persistence.sqlite import SQL_DIR, SqliteBatchRepository

PHARMACIES = 200
DRUGS = 500
CUSTOMERS = 20000
RESERVATIONS_PER_CUSTOMER = 3
RUNS = 200

QUERIES = {
    "UC7, UC2: партії аптеки (SqliteBatchRepository.load_for)":
        (f"{SqliteBatchRepository.SELECT} WHERE b.pharmacy_number = ?", ("А-100",)),
    "UC2: резервування покупця (SqliteReservationRepository.load_for)":
        ("SELECT * FROM reservation WHERE customer_phone = ?", ("+380670012345",)),
}


def build_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
    connection.execute("INSERT INTO pharmacy_chain VALUES (1, 'Мережа', '12345678')")
    connection.executemany("INSERT INTO pharmacy VALUES (?, 1, 'адреса', 'місто', 'тел', 'графік')",
                           [(f"А-{n}",) for n in range(PHARMACIES)])
    connection.executemany("INSERT INTO drug VALUES (?, ?, ?, 'таблетки', '1 мг', 'виробник')",
                           [(n, f"Препарат {n}", f"INN {n % 100}") for n in range(DRUGS)])
    connection.executemany("INSERT INTO drug_series VALUES (?, 'S-1', '2030-01-01')",
                           [(n,) for n in range(DRUGS)])
    connection.executemany(
        """INSERT INTO batch (drug_id, series, pharmacy_number, purchase_price_kop, retail_price_kop, quantity)
           VALUES (?, 'S-1', ?, 100, 200, 10)""",
        [(d, f"А-{p}") for p in range(PHARMACIES) for d in range(DRUGS)])
    connection.executemany("INSERT INTO customer VALUES (?, '')",
                           [(f"+38067{n:07d}",) for n in range(CUSTOMERS)])
    connection.executemany(
        """INSERT INTO reservation (code, created_at, expires_at, quantity, state, customer_phone, batch_id)
           VALUES (?, '2026-01-01', '2026-01-02', 1, 'Видане', ?, 1)""",
        [(f"R-{n}-{k}", f"+38067{n:07d}") for n in range(CUSTOMERS) for k in range(RESERVATIONS_PER_CUSTOMER)])
    return connection


def plan(connection: sqlite3.Connection, sql: str, params: tuple) -> list[str]:
    return [row[3] for row in connection.execute(f"EXPLAIN QUERY PLAN {sql}", params)]


def timing_ms(connection: sqlite3.Connection, sql: str, params: tuple) -> float:
    samples = []
    for _ in range(RUNS):
        start = time.perf_counter()
        connection.execute(sql, params).fetchall()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def report(connection: sqlite3.Connection, title: str) -> dict[str, float]:
    print(title)
    measured: dict[str, float] = {}
    for name, (sql, params) in QUERIES.items():
        print(f"  {name}")
        for line in plan(connection, sql, params):
            print(f"    {line}")
        measured[name] = timing_ms(connection, sql, params)
        print(f"    медіана {measured[name]:.3f} мс")
    return measured


def main() -> int:
    connection = build_database()
    print(f"Партій: {PHARMACIES * DRUGS}, резервувань: {CUSTOMERS * RESERVATIONS_PER_CUSTOMER}\n")
    before = report(connection, "ДО створення індексів")
    connection.executescript((SQL_DIR / "indexes.sql").read_text(encoding="utf-8"))
    connection.execute("ANALYZE")
    print()
    after = report(connection, "ПІСЛЯ створення індексів")
    print()
    for name in QUERIES:
        print(f"{name}: прискорення у {before[name] / after[name]:.0f} разів")
    return 0


if __name__ == "__main__":
    sys.exit(main())
