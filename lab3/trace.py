from __future__ import annotations

import argparse
import ast
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


@dataclass
class Matrix:
    requirements: list[dict]
    use_cases: list[dict]
    tests: dict[str, list[str]] = field(default_factory=dict)

    def linked(self, req_id: str) -> list[str]:
        return [uc["id"] for uc in self.use_cases if req_id in uc.get("requirements", [])]

    def uc_priority(self, use_case: dict) -> int | None:
        known = {r["id"]: r.get("priority") for r in self.requirements}
        values = [known[r] for r in use_case.get("requirements", []) if known.get(r) is not None]
        return min(values) if values else None

    def empty_rows(self, functional_only: bool = False) -> list[dict]:
        rows = [r for r in self.requirements if not self.linked(r["id"])]
        return [r for r in rows if r["type"] == "functional"] if functional_only else rows

    def empty_columns(self) -> list[str]:
        known = {r["id"] for r in self.requirements}
        return [uc["id"] for uc in self.use_cases if not known & set(uc.get("requirements", []))]

    def unknown_references(self) -> list[tuple[str, str]]:
        known = {r["id"] for r in self.requirements}
        return [(uc["id"], ref) for uc in self.use_cases
                for ref in uc.get("requirements", []) if ref not in known]

    def table(self) -> list[list[str]]:
        header = ["Вимога", "Пр.", *[uc["id"] for uc in self.use_cases]]
        if self.tests:
            header.append("Тести")
        rows = [header]
        for req in self.requirements:
            marks = ["x" if req["id"] in uc.get("requirements", []) else "" for uc in self.use_cases]
            row = [req["id"], str(req.get("priority") or "-"), *marks]
            if self.tests:
                row.append(str(len(self.tests.get(req["id"], []))) if req["id"] in self.tests else "")
            rows.append(row)
        footer = ["Пріоритет UC", "", *[str(self.uc_priority(uc) or "-") for uc in self.use_cases]]
        if self.tests:
            footer.append("")
        rows.append(footer)
        return rows


def _marked_requirements(function: ast.FunctionDef) -> list[str]:
    ids: list[str] = []
    for decorator in function.decorator_list:
        if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "req"):
            ids += [arg.value for arg in decorator.args if isinstance(arg, ast.Constant)]
    return ids


def find_tests(directory: str | Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(Path(directory).glob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef):
                for req_id in _marked_requirements(node):
                    found.setdefault(req_id, []).append(node.name)
    return found


def plan_iterations(matrix: Matrix, capacity: int, iterations: int) -> tuple[list[list[dict]], dict[str, str]]:
    def dependencies(use_case: dict) -> set[str]:
        return set(use_case.get("depends_on", [])) | set(use_case.get("include", []))

    pending = sorted(
        matrix.use_cases,
        key=lambda uc: (matrix.uc_priority(uc) or 99, int(uc["id"][2:])),
    )
    planned: set[str] = set()
    plan: list[list[dict]] = []
    for _ in range(iterations):
        current: list[dict] = []
        free = capacity
        progress = True
        while progress:
            progress = False
            for uc in list(pending):
                ready = dependencies(uc) <= planned
                if ready and uc["effort"] <= free:
                    current.append(uc)
                    pending.remove(uc)
                    planned.add(uc["id"])
                    free -= uc["effort"]
                    progress = True
                    break
        plan.append(current)
    reasons = {
        uc["id"]: "бракує потужності" if dependencies(uc) <= planned else "залежність не розподілено"
        for uc in pending
    }
    return plan, reasons


def write_markdown(rows: list[list[str]], path: str | Path) -> None:
    lines = ["# Матриця трасування вимог і варіантів використання", ""]
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("|" + "---|" * len(rows[0]))
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(rows: list[list[str]], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        csv.writer(out, delimiter=";").writerows(rows)


def _names(items: list[str]) -> str:
    return ", ".join(items) if items else "немає"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Матриця трасування та план ітерацій")
    parser.add_argument("srs")
    parser.add_argument("use_cases")
    parser.add_argument("--capacity", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--functional-only", action="store_true")
    parser.add_argument("--tests")
    parser.add_argument("--output", default="RUTM")
    args = parser.parse_args(argv)

    tests = find_tests(args.tests) if args.tests else {}
    matrix = Matrix(load_yaml(args.srs)["requirements"], load_yaml(args.use_cases)["use_cases"], tests)
    rows = matrix.table()
    write_markdown(rows, f"{args.output}.md")
    write_csv(rows, f"{args.output}.csv")
    print(f"Матрицю збережено: {args.output}.md, {args.output}.csv")

    empty = matrix.empty_rows(args.functional_only)
    print("Порожні рядки:", _names([r["id"] for r in empty]))
    print("Порожні стовпці:", _names(matrix.empty_columns()))
    unknown = matrix.unknown_references()
    print("Неіснуючі вимоги:", _names([f"{uc} -> {ref}" for uc, ref in unknown]))

    plan, reasons = plan_iterations(matrix, args.capacity, args.iterations)
    for number, iteration in enumerate(plan, start=1):
        load = sum(uc["effort"] for uc in iteration)
        print(f"Ітерація {number} ({load}/{args.capacity}):", _names([uc["id"] for uc in iteration]))
    print("Не розподілено:", _names([f"{uc} ({why})" for uc, why in reasons.items()]))
    if tests:
        covered = sum(1 for r in matrix.requirements if r["id"] in tests)
        print(f"Вимог із тестами: {covered} із {len(matrix.requirements)}")
    return 1 if empty or matrix.empty_columns() or unknown else 0


if __name__ == "__main__":
    sys.exit(main())
