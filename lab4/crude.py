"""Матриця CRUDE за таблицями сценаріїв (ЛР 4, завдання 2).

Запуск: python crude.py uc7_sale.csv uc2_reserve.csv -k crude_keywords.yaml -o CRUDE.md
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from seq_gen import Row, load_table

LETTER_ORDER = "CRUDE"
# Назви в таблицях сценаріїв пишуться разом, а в доменній моделі через пробіл.
DOMAIN_ALIASES = {"ЕлектроннийРецепт": "Електронний рецепт", "ПозиціяПродажу": "Позиція продажу"}


def load_keywords(path: str | Path) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def letter_for(row: Row, keywords: dict[str, list[str]]) -> str:
    if row.kind == "create":
        return "C"
    action = row.action.lower()
    for letter, words in keywords.items():
        if any(word in action for word in words):
            return letter
    return "E"


def build_matrix(tables: list[list[Row]], keywords: dict[str, list[str]]) -> dict[str, dict[str, set[str]]]:
    """Клієнт -> сервер -> літери. Актори й повернення результатів не є викликами класів."""
    matrix: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for rows in tables:
        messages = [r for r in rows if r.kind in ("call", "create")]
        actor = messages[0].subject
        for row in messages:
            if row.subject != actor:
                matrix[row.subject][row.target].add(letter_for(row, keywords))
    return matrix


def render_markdown(matrix: dict[str, dict[str, set[str]]]) -> str:
    clients = list(matrix)
    servers = list(dict.fromkeys(s for row in matrix.values() for s in row))
    lines = ["# Матриця CRUDE", "", "| Клієнт \\ сервер | " + " | ".join(servers) + " |",
             "|---|" + "---|" * len(servers)]
    for client in clients:
        cells = [" ".join(sorted(matrix[client].get(s, ()), key=LETTER_ORDER.index)) for s in servers]
        lines.append(f"| {client} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def coupling(matrix: dict[str, dict[str, set[str]]]) -> dict[str, tuple[int, int]]:
    """Клас -> (до скількох класів звертається, скільки класів звертається до нього)."""
    classes = list(dict.fromkeys([*matrix, *(s for row in matrix.values() for s in row)]))
    return {c: (len(matrix.get(c, {})), sum(c in row for row in matrix.values())) for c in classes}


def created_but_never_read(matrix: dict[str, dict[str, set[str]]]) -> list[str]:
    letters: dict[str, set[str]] = defaultdict(set)
    for row in matrix.values():
        for server, used in row.items():
            letters[server] |= used
    return [name for name, used in letters.items() if "C" in used and "R" not in used]


def load_domain_links(path: str | Path) -> tuple[set[str], set[frozenset[str]]]:
    """Класи й зв'язки доменної моделі з classification.csv."""
    with open(path, encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    classes = {r["name"] for r in rows if r["code"] in ("C", "AC")}
    links = {frozenset((r["owner"], r["target"])) for r in rows if r["code"] in ("AS", "AG", "I", "AC")}
    links |= {frozenset((r["name"], end)) for r in rows if r["code"] == "AC" for end in (r["owner"], r["target"])}
    return classes, links


def links_missing_in_domain(matrix, classes: set[str], links: set[frozenset[str]]) -> list[str]:
    """Звернення між доменними класами мають спиратися на зв'язок доменної моделі."""
    missing = []
    for client, row in matrix.items():
        for server in row:
            pair = (DOMAIN_ALIASES.get(client, client), DOMAIN_ALIASES.get(server, server))
            if set(pair) <= classes and frozenset(pair) not in links:
                missing.append(f"{pair[0]} -> {pair[1]}")
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Матриця CRUDE")
    parser.add_argument("tables", nargs="+")
    parser.add_argument("-k", "--keywords", default="crude_keywords.yaml")
    parser.add_argument("-o", "--output", default="CRUDE.md")
    parser.add_argument("--domain", default="../lab2/classification.csv")
    args = parser.parse_args(argv)

    matrix = build_matrix([load_table(t) for t in args.tables], load_keywords(args.keywords))
    Path(args.output).write_text(render_markdown(matrix), encoding="utf-8")
    print(f"Збережено: {args.output}")
    print(f"{'Клас':<26}{'звертається до':>15}{'до нього':>10}")
    table = coupling(matrix)
    for name, (fan_out, fan_in) in sorted(table.items(), key=lambda kv: -sum(kv[1])):
        print(f"{name:<26}{fan_out:>15}{fan_in:>10}")
    busiest = max(table, key=lambda name: sum(table[name]))
    print(f"Найбільше зв'язків: {busiest} ({sum(table[busiest])})")
    print("Створюються, але не читаються:", ", ".join(created_but_never_read(matrix)) or "немає")
    classes, links = load_domain_links(args.domain)
    print("Немає в доменній моделі:", ", ".join(links_missing_in_domain(matrix, classes, links)) or "немає")
    return 0


if __name__ == "__main__":
    sys.exit(main())
