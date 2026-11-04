"""Автоматизоване рецензування якості вимог (ЛР 1, завдання 3).

Запуск: python validate.py srs.yaml
Код завершення: 0 - дефектів немає, 1 - дефекти знайдено, 2 - помилка запуску.

Перевірки 1-8 обов'язкові (таблиця 1.3 методичних рекомендацій), 9-13 власні.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations

from srs_model import Specification, load_spec

ID_PATTERN = re.compile(r"^(R\d+(\.\d+)*|N\d+|C\d+)$")
ALLOWED_TYPES = {"functional", "operational", "performance", "security", "cultural", "constraint"}
NON_FUNCTIONAL_TYPES = {"operational", "performance", "security", "cultural"}
OPENINGS = ("іс повинна", "система повинна")

# Основи слів: так одним записом покриваються всі відмінкові форми.
VAGUE_STEMS = (
    "швидк", "зручн", "легк", "тощо", "ефективн", "оптимальн", "інтуїтивн",
    "гнучк", "сучасн", "приблизн", "зрозумі", "достатн", "якісн",
)
IMPLEMENTATION_WORDS = ("кнопк", "кнопц", "таблиц", "сторінк", "сторінц", "mysql", "sqlite", "клас ", "вікн")
# Вимоги з цими темами регулюються законом, тому не можуть мати низький пріоритет.
REGULATED_STEMS = ("рецепт", "персональн")
MAX_REGULATED_PRIORITY = 2
SIMILARITY_THRESHOLD = 0.85


@dataclass(frozen=True)
class Defect:
    req_id: str
    kind: str
    message: str

    def __str__(self) -> str:
        return f"{self.req_id:<7} [{self.kind}] {self.message}"


def normalize(text: str) -> str:
    """Регістр і пробіли не мають впливати на порівняння текстів."""
    return " ".join(text.lower().split())


def _find_stem(text: str, stems: tuple[str, ...]) -> str | None:
    """Шукає основу на початку слова, щоб «незручно» не збігалося із «зручн»."""
    for stem in stems:
        if re.search(rf"\b{re.escape(stem)}", text):
            return stem
    return None


def check_ids(spec: Specification) -> list[Defect]:
    defects = [
        Defect(r.id or "?", "формат", "ID не відповідає шаблону R1 / R1.1 / N1 / C1")
        for r in spec.requirements if not ID_PATTERN.match(r.id)
    ]
    counts = Counter(r.id for r in spec.requirements)
    defects += [
        Defect(req_id, "надлишковість", f"ID повторюється {n} рази")
        for req_id, n in counts.items() if n > 1
    ]
    return defects


def check_types(spec: Specification) -> list[Defect]:
    return [
        Defect(r.id, "формат", f"недопустимий тип «{r.type}»")
        for r in spec.requirements if r.type not in ALLOWED_TYPES
    ]


def check_wording(spec: Specification) -> list[Defect]:
    return [
        Defect(r.id, "формулювання", "немає «ІС повинна…»")
        for r in spec.requirements if not normalize(r.text).startswith(OPENINGS)
    ]


def check_vague_words(spec: Specification) -> list[Defect]:
    defects = []
    for req in spec.requirements:
        stem = _find_stem(normalize(req.text), VAGUE_STEMS)
        if stem:
            defects.append(Defect(req.id, "неоднозначність", f"розмите слово «{stem}…»"))
    return defects


def check_measurable(spec: Specification) -> list[Defect]:
    return [
        Defect(r.id, "неперевірюваність", "немає числового критерію")
        for r in spec.by_type("performance") if not re.search(r"\d", r.text)
    ]


def check_priorities(spec: Specification) -> list[Defect]:
    defects = []
    for req in spec.requirements:
        if req.type == "constraint":
            continue
        # bool є підкласом int, тому True інакше сприймався б як пріоритет 1.
        valid = isinstance(req.priority, int) and not isinstance(req.priority, bool)
        if not valid or not 1 <= req.priority <= 5:
            defects.append(Defect(req.id, "пріоритет", "пріоритет має бути 1..5"))
    return defects


def check_parents(spec: Specification) -> list[Defect]:
    known = {r.id for r in spec.requirements}
    defects = []
    for req in spec.requirements:
        if req.parent is None:
            if "." in req.id:
                defects.append(Defect(req.id, "нетрасованість", "підвимога без батьківської вимоги"))
            continue
        if req.parent not in known:
            defects.append(Defect(req.id, "нетрасованість", f"немає батька {req.parent}"))
        elif not re.fullmatch(re.escape(req.parent) + r"\.\d+", req.id):
            defects.append(Defect(req.id, "нетрасованість", f"ID не продовжує ID батька {req.parent}"))
    return defects


def check_similar(spec: Specification) -> list[Defect]:
    defects = []
    for first, second in combinations(spec.requirements, 2):
        ratio = SequenceMatcher(None, normalize(first.text), normalize(second.text)).ratio()
        if ratio >= SIMILARITY_THRESHOLD:
            defects.append(Defect(second.id, "надлишковість", f"схожа на {first.id} ({ratio:.0%})"))
    return defects


def check_implementation_words(spec: Specification) -> list[Defect]:
    """Власна перевірка 9. Обмеження можуть називати технології, а вимоги ні."""
    defects = []
    for req in spec.requirements:
        if req.type == "constraint":
            continue
        word = _find_stem(normalize(req.text), IMPLEMENTATION_WORDS)
        if word:
            defects.append(Defect(req.id, "деталі реалізації", f"слово реалізації «{word.strip()}…»"))
    return defects


def check_user_story_coverage(spec: Specification) -> list[Defect]:
    """Власна перевірка 10. Кожна user story має породжувати хоча б одну вимогу."""
    sources = " ".join(r.source for r in spec.requirements)
    return [
        Defect(s.id, "неповнота", "історію не згадано в джерелах вимог")
        for s in spec.user_stories if s.id not in sources
    ]


def check_id_prefix_matches_type(spec: Specification) -> list[Defect]:
    """Власна перевірка 11. Префікс ID узгоджений з типом; обмеження без пріоритету."""
    defects = []
    for req in spec.requirements:
        prefix = req.id[:1]
        expected = (
            prefix == "R" and req.type == "functional"
            or prefix == "N" and req.type in NON_FUNCTIONAL_TYPES
            or prefix == "C" and req.type == "constraint"
        )
        if req.type in ALLOWED_TYPES and not expected:
            defects.append(Defect(req.id, "формат", f"префікс ID не відповідає типу {req.type}"))
        if req.type == "constraint" and req.priority is not None:
            defects.append(Defect(req.id, "пріоритет", "обмеження не має мати пріоритету"))
    return defects


def check_sources(spec: Specification) -> list[Defect]:
    """Власна перевірка 12. Вимога без джерела нетрасована до стейкхолдера."""
    return [
        Defect(r.id, "нетрасованість", "не вказано джерело вимоги")
        for r in spec.requirements if not r.source
    ]


def check_regulated_priority(spec: Specification) -> list[Defect]:
    """Власна перевірка 13 (предметна). Рецепти й персональні дані регулює закон."""
    defects = []
    for req in spec.requirements:
        if req.type == "constraint" or not isinstance(req.priority, int):
            continue
        regulated = any(stem in normalize(req.text) for stem in REGULATED_STEMS)
        if regulated and req.priority > MAX_REGULATED_PRIORITY:
            defects.append(Defect(
                req.id, "пріоритет",
                f"регуляторна вимога має пріоритет {req.priority} (> {MAX_REGULATED_PRIORITY})",
            ))
    return defects


CHECKS = (
    check_ids, check_types, check_wording, check_vague_words, check_measurable,
    check_priorities, check_parents, check_similar, check_implementation_words,
    check_user_story_coverage, check_id_prefix_matches_type, check_sources,
    check_regulated_priority,
)


def validate(spec: Specification) -> list[Defect]:
    return [defect for check in CHECKS for defect in check(spec)]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Використання: python validate.py srs.yaml", file=sys.stderr)
        return 2
    spec = load_spec(argv[1])
    defects = validate(spec)
    for defect in defects:
        print(defect)
    print(f"Перевірено {len(spec.requirements)} вимог, знайдено {len(defects)} дефектів")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
