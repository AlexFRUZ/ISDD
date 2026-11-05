from __future__ import annotations

import sys
from pathlib import Path

import yaml

from classification_io import Row, class_names, load_rows

NAME_MAP_FILE = Path(__file__).with_name("name_map.yaml")


def load_aliases(path: Path = NAME_MAP_FILE) -> dict[str, str]:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)["classes"]


def _alias(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name.replace(" ", "_"))


def _ends(mult: str) -> tuple[str, str]:
    first, _, second = mult.partition(";")
    return (f' "{first}"' if first else "", f' "{second}"' if second else "")


def _render_class(name: str, rows: list[Row], aliases: dict[str, str]) -> list[str]:
    attributes = [r for r in rows if r.code == "A" and r.owner == name]
    lines = [f'class "{name}" as {_alias(name, aliases)} {{']
    lines += [f"  {r.attribute_name} : {r.attribute_type}" for r in attributes]
    return lines + ["}"]


def _render_relation(row: Row, aliases: dict[str, str]) -> list[str]:
    owner, target = _alias(row.owner, aliases), _alias(row.target, aliases)
    left, right = _ends(row.mult)
    if row.code == "I":
        return [f"{owner} <|-- {target}"]
    if row.code == "AG":
        return [f"{owner}{left} o--{right} {target} : {row.name} >"]
    if row.code == "AS":
        return [f"{owner}{left} --{right} {target} : {row.name} >"]
    return [f"{owner}{left} --{right} {target}", f"({owner}, {target}) .. {_alias(row.name, aliases)}"]


def build_diagram(rows: list[Row], aliases: dict[str, str]) -> str:
    lines = [
        "@startuml domain",
        "title Доменна модель ІС «Мережа аптек»",
        "skinparam classAttributeIconSize 0",
        "skinparam linetype ortho",
        "skinparam nodesep 75",
        "skinparam ranksep 130",
        "hide circle",
        "hide empty methods",
        "left to right direction",
        "",
    ]
    for name in class_names(rows):
        lines += _render_class(name, rows, aliases)
    lines.append("")
    for row in rows:
        if row.code in ("AS", "AG", "I", "AC"):
            lines += _render_relation(row, aliases)
    return "\n".join(lines + ["@enduml", ""])


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Використання: python dmcd.py classification.csv domain.puml", file=sys.stderr)
        return 2
    rows = load_rows(argv[1])
    with open(argv[2], "w", encoding="utf-8") as out:
        out.write(build_diagram(rows, load_aliases()))
    print(f"Класів: {len(class_names(rows))}. Збережено: {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
