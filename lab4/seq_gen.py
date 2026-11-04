"""Генератор діаграм послідовності за таблицею сценарію (ЛР 4, завдання 1).

Запуск: python seq_gen.py uc7_sale.csv -o uc7_sale.puml
Код завершення: 0 - успіх, 1 - порушення правила Kung або структури фрагментів.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

MESSAGE_KINDS = ("call", "return", "create")
OPENING_KINDS = ("alt", "loop")


@dataclass
class Row:
    no: str
    subject: str
    action: str
    data: str
    target: str
    kind: str

    @property
    def is_message(self) -> bool:
        return self.kind in MESSAGE_KINDS

    @property
    def label(self) -> str:
        return f"{self.action}({self.data})" if self.data else f"{self.action}()"


def load_table(path: str | Path) -> list[Row]:
    with open(path, encoding="utf-8", newline="") as stream:
        return [Row(**{k: (v or "").strip() for k, v in rec.items()})
                for rec in csv.DictReader(stream, delimiter=";")]


def check_kung_rule(rows: list[Row]) -> list[str]:
    """Суб'єкт рядка має бути об'єктом дії попереднього рядка або суб'єктом одного з попередніх."""
    violations: list[str] = []
    messages = [r for r in rows if r.is_message]
    seen_subjects: set[str] = set()
    for previous, current in zip([None, *messages], messages):
        if previous is not None and current.subject != previous.target and current.subject not in seen_subjects:
            violations.append(
                f'Рядок {current.no}: суб\'єкт "{current.subject}" не є об\'єктом дії рядка {previous.no}\n'
                f"         і не був суб'єктом попередніх рядків"
            )
        seen_subjects.add(current.subject)
    return violations


def check_fragments(rows: list[Row]) -> list[str]:
    """Кожен фрагмент має закриватися, а else може стояти лише всередині alt."""
    errors: list[str] = []
    stack: list[str] = []
    for row in rows:
        if row.kind in OPENING_KINDS:
            stack.append(row.kind)
        elif row.kind == "else" and (not stack or stack[-1] != "alt"):
            errors.append(f"Рядок {row.no}: else поза фрагментом alt")
        elif row.kind == "end":
            if stack:
                stack.pop()
            else:
                errors.append(f"Рядок {row.no}: end без відкритого фрагмента")
    errors += [f"Фрагмент {kind} не закрито" for kind in stack]
    return errors


def participants(rows: list[Row]) -> list[str]:
    """Учасники в порядку першої появи."""
    names: dict[str, None] = {}
    for row in rows:
        if row.is_message:
            names.setdefault(row.subject)
            names.setdefault(row.target)
    return list(names)


def _declaration(name: str, alias: str, actor: str, created: set[str]) -> str:
    if name == actor:
        keyword = "actor"
    elif name.endswith("UI"):
        keyword = "boundary"
    elif name.startswith("Контролер"):
        keyword = "control"
    else:
        keyword = "participant"
    # Об'єкт, створений у сценарії, оголошується в момент створення.
    return "" if name in created else f'{keyword} "{name}" as {alias}'


def build_diagram(rows: list[Row], title: str) -> str:
    names = participants(rows)
    alias = {name: f"P{i}" for i, name in enumerate(names, start=1)}
    created = {r.target for r in rows if r.kind == "create"}
    actor = next(r.subject for r in rows if r.is_message)
    lines = [f"@startuml {title}", f"title Діаграма послідовності {title}", "hide footbox", ""]
    lines += [d for name in names if (d := _declaration(name, alias[name], actor, created))]
    lines.append("")
    declared: set[str] = set()
    for row in rows:
        if row.kind == "call":
            lines.append(f"{alias[row.subject]} -> {alias[row.target]} : {row.label}")
        elif row.kind == "return":
            lines.append(f"{alias[row.subject]} --> {alias[row.target]} : {row.label}")
        elif row.kind == "create":
            if row.target not in declared:
                lines.append(f'create participant "{row.target}" as {alias[row.target]}')
                declared.add(row.target)
            lines.append(f"{alias[row.subject]} -> {alias[row.target]} : {row.label}")
        elif row.kind in ("alt", "loop", "else"):
            lines.append(f"{row.kind} {row.action}")
        elif row.kind == "end":
            lines.append("end")
    return "\n".join(lines + ["@enduml", ""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Діаграма послідовності за таблицею сценарію")
    parser.add_argument("table")
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)

    rows = load_table(args.table)
    problems = check_kung_rule(rows)
    fragment_errors = check_fragments(rows)
    if problems or fragment_errors:
        print("\n".join(problems + fragment_errors))
        print(f"Знайдено порушень: {len(problems) + len(fragment_errors)}")
        return 1

    output = Path(args.output) if args.output else Path(args.table).with_suffix(".puml")
    output.write_text(build_diagram(rows, output.stem), encoding="utf-8")
    messages = sum(r.is_message for r in rows)
    fragments = sum(r.kind in OPENING_KINDS for r in rows)
    print(f"Учасників: {len(participants(rows))}, повідомлень: {messages}, фрагментів: {fragments}")
    print("Перевірку правила Kung пройдено")
    print(f"Збережено: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
