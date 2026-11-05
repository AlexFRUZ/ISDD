from __future__ import annotations

import sys
from collections import Counter

from srs_model import Requirement, Specification, id_sort_key, load_spec

TYPE_TITLES = {
    "functional": "Функціональні вимоги",
    "operational": "Операційні вимоги",
    "performance": "Вимоги продуктивності",
    "security": "Вимоги безпеки",
    "cultural": "Культурні та політичні вимоги",
    "constraint": "Обмеження проєктування",
}


def _priority_label(req: Requirement) -> str:
    return "" if req.priority is None else f" *(пріоритет {req.priority})*"


def _render_tree(spec: Specification, req: Requirement, depth: int = 0) -> list[str]:
    lines = [f"{'  ' * depth}- **{req.id}**{_priority_label(req)}. {req.text}"]
    for child in spec.children(req.id):
        lines += _render_tree(spec, child, depth + 1)
    return lines


def _render_requirements(spec: Specification) -> list[str]:
    lines: list[str] = []
    for index, (req_type, title) in enumerate(TYPE_TITLES.items(), start=1):
        roots = sorted(
            (r for r in spec.by_type(req_type) if not r.parent),
            key=lambda r: id_sort_key(r.id),
        )
        if not roots:
            continue
        lines += [f"### 3.{index} {title}", ""]
        for root in roots:
            lines += _render_tree(spec, root)
        lines.append("")
    return lines


def _render_statistics(spec: Specification) -> list[str]:
    by_type = Counter(r.type for r in spec.requirements)
    by_priority = Counter(r.priority for r in spec.requirements)
    lines = ["## 4. Статистика вимог", "", "| Тип | Кількість |", "|---|---|"]
    lines += [f"| {TYPE_TITLES.get(t, t)} | {by_type[t]} |" for t in TYPE_TITLES if by_type[t]]
    lines += [f"| **Разом** | **{len(spec.requirements)}** |", ""]
    lines += ["| Пріоритет | Кількість |", "|---|---|"]
    lines += [f"| {p} | {by_priority[p]} |" for p in range(1, 6) if by_priority[p]]
    if by_priority[None]:
        lines.append(f"| без пріоритету (обмеження) | {by_priority[None]} |")
    return lines + [""]


def build_report(spec: Specification) -> str:
    request = spec.system_request
    top_functions = sorted(
        (r for r in spec.by_type("functional") if not r.parent),
        key=lambda r: id_sort_key(r.id),
    )
    lines = [
        f"# Специфікація вимог до ПЗ: {spec.project}",
        "",
        "## 1. Вступ",
        "",
        f"**Проєкт:** {spec.project}.",
        "",
        f"**Спонсор:** {request.sponsor}.",
        "",
        f"**Бізнес-потреба:** {request.business_need}",
        "",
        "## 2. Загальний опис",
        "",
        "### 2.1 Функції продукту",
        "",
        *[f"- {r.id}: {r.text}" for r in top_functions],
        "",
        "### 2.2 Користувачі",
        "",
        *[f"- {s}" for s in spec.stakeholders],
        "",
        "### 2.3 Обмеження",
        "",
        *[f"- {c}" for c in request.constraints],
        "",
        "## 3. Специфічні вимоги",
        "",
        *_render_requirements(spec),
        *_render_statistics(spec),
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Використання: python srs_report.py srs.yaml SRS.md", file=sys.stderr)
        return 2
    spec = load_spec(argv[1])
    with open(argv[2], "w", encoding="utf-8") as out:
        out.write(build_report(spec))
    print(f"Збережено: {argv[2]} (вимог: {len(spec.requirements)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
