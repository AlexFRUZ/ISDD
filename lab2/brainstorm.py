"""Збір результатів брейнштормінгу з розміченого тексту (ЛР 2, завдання 1).

Формат розмітки: [фраза]{номер правила 1-9}. Українська мова флективна, тому
розмітку розширено: [аптек|аптека]{1} означає, що в тексті стоїть «аптек», а
дублікати рахуються за нормальною формою «аптека».

Запуск: python brainstorm.py domain.txt brainstorm.csv
Код завершення: 0 - успіх, 1 - некоректна розмітка, 2 - помилка запуску.
"""
from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass

MARKUP = re.compile(r"\[([^\[\]]*)\]\{(\d+)\}")
MIN_RULE, MAX_RULE = 1, 9


@dataclass
class Phrase:
    text: str
    rule: int
    count: int = 1


def normalize_phrase(raw: str) -> str:
    """Бере нормальну форму, якщо вона є, і прибирає різницю в регістрі та пробілах."""
    canonical = raw.split("|")[-1]
    return " ".join(canonical.lower().split())


def find_markup_errors(text: str) -> list[str]:
    """Повертає повідомлення про незакриті дужки та неправильні номери правил."""
    errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in MARKUP.finditer(line):
            if not match.group(1).strip():
                errors.append(f"Рядок {line_no}: порожня фраза")
            rule = int(match.group(2))
            if not MIN_RULE <= rule <= MAX_RULE:
                errors.append(f"Рядок {line_no}: номер правила {rule} поза діапазоном 1-9 у «{match.group(1)}»")
        rest = MARKUP.sub("", line)  # після вилучення коректних елементів дужок не лишається
        if "[" in rest:
            errors.append(f"Рядок {line_no}: незакрита дужка «[» або вкладена розмітка")
        if "]" in rest:
            errors.append(f"Рядок {line_no}: зайва дужка «]» або немає номера правила {{n}}")
    return errors


def collect_phrases(text: str) -> list[Phrase]:
    """Видаляє дублікати, зберігаючи порядок першої появи фрази."""
    phrases: dict[tuple[str, int], Phrase] = {}
    for match in MARKUP.finditer(text):
        key = (normalize_phrase(match.group(1)), int(match.group(2)))
        if key in phrases:
            phrases[key].count += 1
        else:
            phrases[key] = Phrase(*key)
    return list(phrases.values())


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Використання: python brainstorm.py domain.txt brainstorm.csv", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as stream:
        text = stream.read()
    errors = find_markup_errors(text)
    if errors:
        print("\n".join(errors))
        print(f"Некоректна розмітка, помилок: {len(errors)}. Файл не збережено.")
        return 1
    phrases = collect_phrases(text)
    with open(argv[2], "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["phrase", "rule", "count"])
        writer.writerows((p.text, p.rule, p.count) for p in phrases)
    print(f"Унікальних фраз: {len(phrases)}. Збережено: {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
