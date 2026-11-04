"""Метрики якості проєкту класів (ЛР 6, завдання 3).

Запуск: python metrics.py ../pharmacy --max-methods 10 --max-fanout 5 --max-dit 3

Для кожного класу обчислюються: кількість методів і атрибутів, глибина дерева
успадкування (DIT) у межах проєкту, fan-out (скільки інших класів проєкту використовує
клас) і fan-in (скільки класів проєкту використовують цей клас). Посиланням вважається
будь-яке ім'я класу в тілі класу: анотація типу, створення об'єкта чи виклик. Імпорт,
який клас не використовує, не рахується, бо модуль може містити кілька класів.

Додатково рахується кількість точок рішення (розгалуження, цикли, логічні оператори).
Fan-out показує, про які типи знає клас, а точки рішення показують, скільки логіки він
виконує сам. Тому перенесення правил із контролера в доменний клас помітно саме тут.
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONSTRUCTORS = ("__init__", "__post_init__")
DECISION_NODES = (ast.If, ast.For, ast.While, ast.IfExp, ast.BoolOp, ast.comprehension, ast.ExceptHandler)


@dataclass
class ClassInfo:
    name: str
    module: str
    methods: int = 0
    attributes: int = 0
    bases: list[str] = field(default_factory=list)
    names_used: set[str] = field(default_factory=set)
    decisions: int = 0
    dit: int = 0
    fan_in: int = 0
    fan_out: int = 0


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    return node.attr if isinstance(node, ast.Attribute) else ""


def _count_attributes(node: ast.ClassDef) -> int:
    """Анотовані поля класу та присвоєння self.x у конструкторі."""
    names = {s.target.id for s in node.body
             if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)}
    for method in node.body:
        if isinstance(method, ast.FunctionDef) and method.name in CONSTRUCTORS:
            for item in ast.walk(method):
                targets = item.targets if isinstance(item, ast.Assign) else (
                    [item.target] if isinstance(item, ast.AnnAssign) else [])
                names |= {t.attr for t in targets if isinstance(t, ast.Attribute)
                          and isinstance(t.value, ast.Name) and t.value.id == "self"}
    return len(names)


def analyse_class(node: ast.ClassDef, module: str) -> ClassInfo:
    methods = [s for s in node.body if isinstance(s, ast.FunctionDef) and s.name not in CONSTRUCTORS]
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    used |= {n.value for n in ast.walk(node)
             if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.isidentifier()}
    decisions = sum(isinstance(n, DECISION_NODES) for n in ast.walk(node))
    # Фільтр у comprehension є полем ifs, а не вузлом ast.If, тому його рахуємо окремо.
    decisions += sum(len(n.ifs) for n in ast.walk(node) if isinstance(n, ast.comprehension))
    return ClassInfo(node.name, module, len(methods), _count_attributes(node),
                     [_base_name(b) for b in node.bases], used, decisions)


def collect_classes(root: Path) -> dict[str, ClassInfo]:
    classes: dict[str, ClassInfo] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes[node.name] = analyse_class(node, path.stem)
    return classes


def _depth(name: str, classes: dict[str, ClassInfo]) -> int:
    parents = [b for b in classes[name].bases if b in classes]
    return 1 + max(_depth(p, classes) for p in parents) if parents else 0


def compute_metrics(classes: dict[str, ClassInfo]) -> dict[str, ClassInfo]:
    for info in classes.values():
        info.dit = _depth(info.name, classes)
        references = (info.names_used & set(classes)) - {info.name}
        info.fan_out = len(references)
        for other in references:
            classes[other].fan_in += 1
    return classes


def warnings(classes: dict[str, ClassInfo], max_methods: int, max_fanout: int, max_dit: int) -> list[str]:
    found: list[str] = []
    for info in classes.values():
        if info.methods > max_methods:
            found.append(f"УВАГА: {info.name} – методів {info.methods} (> {max_methods})")
        if info.fan_out > max_fanout:
            found.append(f"УВАГА: {info.name} – fan-out {info.fan_out} (> {max_fanout})")
        if info.dit > max_dit:
            found.append(f"УВАГА: {info.name} – DIT {info.dit} (> {max_dit})")
    return found


def render_table(classes: dict[str, ClassInfo]) -> list[str]:
    lines = [f"{'Клас':<30}{'метод.':>7}{'атриб.':>7}{'DIT':>5}{'fan-in':>8}{'fan-out':>9}{'рішень':>8}"]
    for info in sorted(classes.values(), key=lambda c: (c.module, c.name)):
        lines.append(f"{info.name:<30}{info.methods:>7}{info.attributes:>7}{info.dit:>5}"
                     f"{info.fan_in:>8}{info.fan_out:>9}{info.decisions:>8}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Метрики класів проєкту")
    parser.add_argument("package")
    parser.add_argument("--max-methods", type=int, default=10)
    parser.add_argument("--max-fanout", type=int, default=5)
    parser.add_argument("--max-dit", type=int, default=3)
    args = parser.parse_args(argv)

    classes = compute_metrics(collect_classes(Path(args.package)))
    print("\n".join(render_table(classes)))
    found = warnings(classes, args.max_methods, args.max_fanout, args.max_dit)
    print("\n".join(found) if found else "Попереджень немає")
    average = sum(c.fan_out for c in classes.values()) / len(classes)
    print(f"Класів: {len(classes)}. Середній fan-out: {average:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
