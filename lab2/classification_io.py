"""Спільне читання classification.csv для dmcd.py, review.py і test_conformance.py."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

RELATION_CODES = ("AS", "AG", "I", "AC")


@dataclass
class Row:
    phrase: str
    code: str
    name: str
    owner: str
    target: str
    mult: str
    rule: str
    note: str

    @property
    def attribute_name(self) -> str:
        """Назва атрибута без типу: «серія : String» дає «серія»."""
        return self.name.split(":")[0].strip()

    @property
    def attribute_type(self) -> str:
        return self.name.split(":")[1].strip() if ":" in self.name else "String"


def load_rows(path: str | Path) -> list[Row]:
    with open(path, encoding="utf-8", newline="") as stream:
        return [Row(**{k: (v or "").strip() for k, v in rec.items()}) for rec in csv.DictReader(stream)]


def class_names(rows: list[Row]) -> list[str]:
    """Класи й асоціативні класи в порядку першої появи."""
    return list(dict.fromkeys(r.name for r in rows if r.code in ("C", "AC")))
