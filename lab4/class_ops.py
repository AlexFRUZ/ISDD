from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from crude import DOMAIN_ALIASES
from seq_gen import load_table


def collect_operations(paths: list[str]) -> dict[str, list[str]]:
    operations: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        for row in load_table(path):
            if row.kind == "call":
                name = DOMAIN_ALIASES.get(row.target, row.target)
                if row.label not in operations[name]:
                    operations[name].append(row.label)
    return operations


def add_operations(puml: str, operations: dict[str, list[str]]) -> tuple[str, int]:
    added = 0
    for name, labels in operations.items():
        pattern = re.compile(rf'(class "{re.escape(name)}" as \w+ \{{\n(?:.*\n)*?)(\}})')
        if pattern.search(puml):
            body = "  --\n" + "".join(f"  {label}\n" for label in labels)
            puml = pattern.sub(lambda m, b=body: m.group(1) + b + m.group(2), puml, count=1)
            added += len(labels)
    text = puml.replace("hide empty methods\n", "").replace("Доменна модель", "Доменні класи з операціями")
    return text.replace("@startuml domain", "@startuml domain_ops"), added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Додає операції до діаграми класів")
    parser.add_argument("tables", nargs="+")
    parser.add_argument("--domain", default="../lab2/domain.puml")
    parser.add_argument("-o", "--output", default="diagrams/domain_ops.puml")
    args = parser.parse_args(argv)
    text, added = add_operations(Path(args.domain).read_text(encoding="utf-8"), collect_operations(args.tables))
    Path(args.output).write_text(text, encoding="utf-8")
    print(f"Додано операцій: {added}. Збережено: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
