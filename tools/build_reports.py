"""Збирає звіти labN/REPORT.md із вихідних файлів labN/REPORT.src.md.

Запуск: python tools/build_reports.py

Код і результати підставляються з реальних файлів, тому звіт не розходиться з проєктом.
Директиви (рядок цілком):
  <!-- md: шлях -->                вставити Markdown
  <!-- txt: шлях [мова] -->        вставити файл блоком коду
  <!-- py: шлях Клас.метод -->     вставити клас або функцію Python
  <!-- sql: шлях таблиця -->       вставити CREATE TABLE
  <!-- table: use_cases -->        таблиця меж варіантів використання
Запис md@lab5, py@lab5 тощо бере файл зі стану за тегом Git, щоб звіт показував код
свого етапу, а не фінальну версію.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DIRECTIVE = re.compile(r"^<!-- (\w+)(?:@(\w+))?: (.+?) -->$")
HEADING = re.compile(r"^(#+) ")
COURSE = "Проєктування та розробка інформаційних систем"
STUDENT = "Гладун Олександр Володимирович"
GROUP = "КНм-26-1"


def read_source(lab_dir: Path, path: str, tag: str | None) -> str:
    target = (lab_dir / path).resolve()
    if tag is None:
        return target.read_text(encoding="utf-8")
    relative = target.relative_to(ROOT).as_posix()
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{tag}:{relative}"],
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout


def extract_python(source: str, dotted: str) -> str:
    """Вихідний текст класу чи функції разом із декораторами, зокрема Клас.метод."""
    node: ast.AST = ast.parse(source)
    for name in dotted.split("."):
        node = next(n for n in node.body
                    if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    first = min([d.lineno for d in node.decorator_list] + [node.lineno]) - 1
    lines = source.splitlines()[first:node.end_lineno]
    indent = len(lines[0]) - len(lines[0].lstrip())
    return "\n".join(line[indent:] for line in lines)


def extract_table(source: str, table: str) -> str:
    match = re.search(rf"^CREATE TABLE {table} \(.*?^\);", source, re.S | re.M)
    return match.group(0)


def shift_headings(text: str, base: int, keep_title: bool) -> str:
    """Понижує заголовки вставленого файлу, щоб вони лягли під поточний розділ."""
    result = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match and len(match.group(1)) == 1 and not keep_title:
            continue
        if match:
            line = "#" * min(len(match.group(1)) + base, 6) + line[len(match.group(1)):]
        result.append(line)
    return "\n".join(result).strip()


def fenced(text: str, language: str = "text") -> str:
    return f"```{language}\n{text.rstrip()}\n```"


def use_cases_table(lab_dir: Path) -> str:
    model = yaml.safe_load((lab_dir / "use_cases.yaml").read_text(encoding="utf-8"))
    rows = ["| ID | Назва | Актори | TUCBW | TUCEW |", "|---|---|---|---|---|"]
    rows += [f"| {u['id']} | {u['name']} | {', '.join(u['actors'])} | {u['tucbw']} | {u['tucew']} |"
             for u in model["use_cases"]]
    return "\n".join(rows)


def expand(kind: str, tag: str | None, argument: str, lab_dir: Path, base: int, keep_title: bool) -> str:
    if kind == "table":
        return use_cases_table(lab_dir)
    path, _, extra = argument.partition(" ")
    source = read_source(lab_dir, path, tag)
    if kind == "md":
        return shift_headings(source, base, keep_title)
    if kind == "txt":
        return fenced(source, extra or "text")
    if kind == "py":
        return fenced(extract_python(source, extra), "python")
    if kind == "sql":
        return fenced(extract_table(source, extra), "sql")
    raise ValueError(f"Невідома директива: {kind}")


def title_block(number: int, title: str) -> list[str]:
    return [
        f"# Звіт про виконання лабораторної роботи № {number}", "",
        "| | |", "|---|---|",
        "| **Заклад** | Хмельницький національний університет, кафедра комп'ютерних наук |",
        f"| **Дисципліна** | {COURSE} |",
        f"| **Тема** | {title} |",
        "| **Варіант** | 3, «Мережа аптек» |",
        f"| **Виконав** | {STUDENT}, група {GROUP} |",
        "| **Перевірив** | |",
        "| **Рік** | Хмельницький, 2026 |", "",
    ]


def build(lab_dir: Path) -> Path:
    text = (lab_dir / "REPORT.src.md").read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    meta = yaml.safe_load(front)
    output = title_block(meta["lab"], meta["title"])
    base = 1
    previous = ""
    for line in body.strip().splitlines():
        heading = HEADING.match(line)
        if heading:
            base = len(heading.group(1))
        directive = DIRECTIVE.match(line.strip())
        if directive:
            kind, tag, argument = directive.groups()
            line = expand(kind, tag, argument, lab_dir, base, keep_title=not previous.startswith("#"))
        output.append(line)
        if line.strip():
            previous = line
    path = lab_dir / "REPORT.md"
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return path


def main() -> int:
    for lab_dir in sorted(ROOT.glob("lab[1-7]")):
        path = build(lab_dir)
        print(f"{path.relative_to(ROOT)}: {len(path.read_text(encoding='utf-8').splitlines())} рядків")
    return 0


if __name__ == "__main__":
    sys.exit(main())
