from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Import:
    file: str
    line: int
    source: str
    target: str
    module: str


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"ПОРУШЕННЯ {self.file}:{self.line}\n  {self.message}"


def load_rules(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def module_of(path: Path, root: Path) -> str:
    parts = path.relative_to(root.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _resolve(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    if node.level == 0:
        return node.module or ""
    base = module.split(".")
    base = base[:len(base) - node.level + (1 if is_package else 0)]
    return ".".join(base + ([node.module] if node.module else []))


def imported_names(tree: ast.AST, module: str, is_package: bool) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((node.lineno, _resolve(node, module, is_package)))
    return found


def layer_of(module: str, package: str) -> str:
    parts = module.split(".")
    return parts[1] if parts[0] == package and len(parts) > 1 else ""


def collect_imports(root: Path, package: str) -> tuple[list[Import], int]:
    imports: list[Import] = []
    files = sorted(root.rglob("*.py"))
    for path in files:
        module = module_of(path, root)
        source = layer_of(module, package)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for line, name in imported_names(tree, module, path.name == "__init__.py"):
            imports.append(Import(path.relative_to(root.parent).as_posix(), line, source,
                                  layer_of(name, package), name))
    return imports, len(files)


def find_violations(imports: list[Import], rules: dict) -> list[Violation]:
    layers = rules["layers"]
    allowed = rules["allowed"]
    forbidden = rules.get("forbidden_modules", {})
    violations: list[Violation] = []
    for item in imports:
        if not item.source:
            continue
        if item.target and item.target != item.source and item.target not in allowed[item.source]:
            upward = layers.index(item.target) < layers.index(item.source)
            reason = "заборонено: залежність угору" if upward else "заборонено правилами рівня"
            violations.append(Violation(item.file, item.line, f"{item.source} -> {item.target} ({reason})"))
        top_level = item.module.split(".")[0]
        if top_level in forbidden.get(item.source, []):
            violations.append(Violation(
                item.file, item.line, f"{item.source} імпортує заборонений модуль {top_level}"))
    return violations


def package_graph(imports: list[Import]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for item in imports:
        if item.source and item.target and item.source != item.target:
            graph[item.source].add(item.target)
    return graph


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node):] + [node]
            if not any(set(cycle) == set(known) for known in cycles):
                cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        for neighbour in sorted(graph.get(node, ())):
            visit(neighbour, [*path, node])

    for start in sorted(graph):
        visit(start, [])
    return cycles


def package_statistics(graph: dict[str, set[str]], layers: list[str]) -> dict[str, tuple[int, int]]:
    return {layer: (sum(layer in targets for targets in graph.values()), len(graph.get(layer, ())))
            for layer in layers}


def build_actual_diagram(graph: dict[str, set[str]], layers: list[str]) -> str:
    lines = ["@startuml actual_packages", "title Фактичні залежності між пакетами", "skinparam packageStyle folder", ""]
    lines += [f'package "{layer}" as {layer} {{\n}}' for layer in layers]
    lines.append("")
    lines += [f"{source} ..> {target}" for source in layers for target in sorted(graph.get(source, ()))]
    return "\n".join(lines + ["@enduml", ""])


def compare_with_rules(graph: dict[str, set[str]], rules: dict) -> tuple[list[str], list[str]]:
    extra, unused = [], []
    for source, allowed in rules["allowed"].items():
        actual = graph.get(source, set())
        extra += [f"{source} -> {t}" for t in sorted(actual - set(allowed))]
        unused += [f"{source} -> {t}" for t in allowed if t not in actual]
    return extra, unused


def check(root: Path, rules: dict) -> tuple[list[Violation], list[list[str]], dict[str, set[str]], int, int]:
    imports, modules = collect_imports(root, rules["package"])
    graph = package_graph(imports)
    cross = sum(1 for i in imports if i.source and i.target and i.source != i.target)
    return find_violations(imports, rules), find_cycles(graph), graph, modules, cross


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Перевірка архітектурних обмежень")
    parser.add_argument("package")
    parser.add_argument("--rules", default="layers.yaml")
    parser.add_argument("-o", "--output", default="actual_packages.puml")
    args = parser.parse_args(argv)

    rules = load_rules(args.rules)
    violations, cycles, graph, modules, cross = check(Path(args.package).resolve(), rules)
    print(f"Модулів: {modules}, імпортів між пакетами: {cross}")
    for violation in violations:
        print(violation)
    print("Цикли:", "; ".join(" -> ".join(c) for c in cycles) if cycles else "немає")
    print(f"{'Пакет':<14}{'вхідні':>8}{'вихідні':>9}")
    for layer, (incoming, outgoing) in package_statistics(graph, rules["layers"]).items():
        print(f"{layer:<14}{incoming:>8}{outgoing:>9}")
    extra, unused = compare_with_rules(graph, rules)
    print("Немає в задумі:", ", ".join(extra) or "немає")
    print("Задумано, але не використано:", ", ".join(unused) or "немає")
    Path(args.output).write_text(build_actual_diagram(graph, rules["layers"]), encoding="utf-8")
    print(f"Збережено: {args.output}")
    return 1 if violations or cycles else 0


if __name__ == "__main__":
    sys.exit(main())
