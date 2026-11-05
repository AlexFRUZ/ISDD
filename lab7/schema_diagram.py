from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "pharmacy" / "persistence" / "schema.sql"


def tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    return [row[0] for row in rows]


def render_table(connection: sqlite3.Connection, table: str) -> list[str]:
    foreign = {row[3] for row in connection.execute(f"PRAGMA foreign_key_list({table})")}
    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
    keys = [c for c in columns if c[5]]
    others = [c for c in columns if not c[5]]

    def line(column: tuple) -> str:
        _, name, column_type, not_null, _, primary = column
        marks = (["PK"] if primary else []) + (["FK"] if name in foreign else [])
        suffix = f" <<{', '.join(marks)}>>" if marks else ""
        return f"  {'*' if not_null or primary else ''} {name} : {column_type}{suffix}"

    return [f'entity "{table}" as {table} {{', *map(line, keys), "  --", *map(line, others), "}"]


def render_links(connection: sqlite3.Connection, table: str) -> list[str]:
    referenced = {row[2] for row in connection.execute(f"PRAGMA foreign_key_list({table})")}
    return [f"{table} }}o--|| {target}" for target in sorted(referenced)]


def build_diagram(connection: sqlite3.Connection) -> str:
    names = tables(connection)
    lines = ["@startuml schema", "title Реляційна схема ІС «Мережа аптек»", "hide circle",
             "skinparam linetype ortho", "skinparam nodesep 50", "skinparam ranksep 60", ""]
    for table in names:
        lines += render_table(connection, table)
    lines.append("")
    for table in names:
        lines += render_links(connection, table)
    return "\n".join(lines + ["@enduml", ""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Діаграма реляційної схеми")
    parser.add_argument("-o", "--output", default="diagrams/schema.puml")
    args = parser.parse_args(argv)
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    Path(args.output).write_text(build_diagram(connection), encoding="utf-8")
    print(f"Таблиць: {len(tables(connection))}. Збережено: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
