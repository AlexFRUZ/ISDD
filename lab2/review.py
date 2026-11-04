"""Автоматичне рецензування класифікації за контрольним списком Kung (ЛР 2, завдання 2).

Запуск: python review.py classification.csv
Код завершення: 0 - зауважень немає, 1 - зауваження є, 2 - помилка запуску.
"""
from __future__ import annotations

import sys
from collections import Counter

from classification_io import RELATION_CODES, Row, class_names, load_rows


def _relations(rows: list[Row]) -> list[Row]:
    return [r for r in rows if r.code in RELATION_CODES]


def check_classes_without_attributes(rows: list[Row]) -> list[str]:
    owners = {r.owner for r in rows if r.code == "A"}
    return [f"Клас «{c}» не має атрибутів" for c in class_names(rows) if c not in owners]


def check_isolated_classes(rows: list[Row]) -> list[str]:
    linked = {name for r in _relations(rows) for name in (r.owner, r.target)}
    linked |= {r.name for r in rows if r.code == "AC"}
    return [f"Клас «{c}» ізольований: немає жодного зв'язку" for c in class_names(rows) if c not in linked]


def check_missing_multiplicities(rows: list[Row]) -> list[str]:
    return [
        f"Зв'язок «{r.owner} {r.name} {r.target}» не має кратностей"
        for r in _relations(rows)
        if r.code != "I" and len([m for m in r.mult.split(";") if m]) != 2
    ]


def check_unknown_classes(rows: list[Row]) -> list[str]:
    known = set(class_names(rows))
    remarks = []
    for row in _relations(rows):
        remarks += [
            f"Зв'язок «{row.phrase}» посилається на неіснуючий клас «{name}»"
            for name in (row.owner, row.target) if name not in known
        ]
    remarks += [
        f"Атрибут «{r.attribute_name}» належить неіснуючому класу «{r.owner}»"
        for r in rows if r.code == "A" and r.owner not in known
    ]
    return remarks


def check_class_as_attribute(rows: list[Row]) -> list[str]:
    known = {c.lower() for c in class_names(rows)}
    return [
        f"Атрибут «{r.attribute_name}» класу «{r.owner}» збігається з назвою класу: потрібен зв'язок"
        for r in rows
        if r.code == "A" and (r.attribute_name.lower() in known or r.attribute_type.lower() in known)
    ]


def check_duplicate_classes(rows: list[Row]) -> list[str]:
    counts = Counter(r.name for r in rows if r.code in ("C", "AC"))
    return [f"Клас «{name}» визначено {n} рази" for name, n in counts.items() if n > 1]


CHECKS = (
    check_classes_without_attributes, check_isolated_classes, check_missing_multiplicities,
    check_unknown_classes, check_class_as_attribute, check_duplicate_classes,
)


def review(rows: list[Row]) -> list[str]:
    return [remark for check in CHECKS for remark in check(rows)]


def summary(rows: list[Row]) -> str:
    codes = Counter(r.code for r in rows)
    return (f"Класів: {codes['C'] + codes['AC']}, атрибутів: {codes['A']}, "
            f"зв'язків: {codes['AS'] + codes['AG'] + codes['I'] + codes['AC']} "
            f"(AS {codes['AS']}, AG {codes['AG']}, I {codes['I']}, AC {codes['AC']})")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Використання: python review.py classification.csv", file=sys.stderr)
        return 2
    rows = load_rows(argv[1])
    remarks = review(rows)
    for remark in remarks:
        print(remark)
    print(summary(rows))
    print(f"Зауважень: {len(remarks)}")
    return 1 if remarks else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
