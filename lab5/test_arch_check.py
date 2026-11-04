"""Тести arch_check.py і тест архітектури реального проєкту (ЛР 5, завдання 3)."""
from pathlib import Path

import pytest

import arch_check as ac

HERE = Path(__file__).parent
PROJECT_PACKAGE = HERE.parent / "pharmacy"
RULES = ac.load_rules(HERE / "layers.yaml")
TOY_RULES = {
    "package": "shop",
    "layers": ["ui", "domain"],
    "allowed": {"ui": ["domain"], "domain": []},
    "forbidden_modules": {"domain": ["sqlite3"]},
}


def make_package(tmp_path, files):
    root = tmp_path / "shop"
    for name, text in {"__init__.py": "", "ui/__init__.py": "", "domain/__init__.py": "", **files}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def messages(root, rules=TOY_RULES):
    return [v.message for v in ac.check(root, rules)[0]]


def test_project_respects_architecture():
    """Порушення шарів, цикл або заборонений модуль ламає цей тест."""
    violations, cycles, *_ = ac.check(PROJECT_PACKAGE.resolve(), RULES)
    assert [str(v) for v in violations] == [] and cycles == []


def test_project_uses_only_planned_dependencies():
    graph = ac.check(PROJECT_PACKAGE.resolve(), RULES)[2]
    assert ac.compare_with_rules(graph, RULES)[0] == []


def test_domain_does_not_depend_on_storage_or_interface():
    graph = ac.check(PROJECT_PACKAGE.resolve(), RULES)[2]
    assert graph["domain"] <= {"foundation"}


def test_allowed_dependency_passes(tmp_path):
    assert messages(make_package(tmp_path, {"ui/cli.py": "import shop.domain.item\n",
                                            "domain/item.py": ""})) == []


def test_upward_dependency_is_reported_with_file_and_line(tmp_path):
    root = make_package(tmp_path, {"domain/item.py": "\n\nfrom shop.ui import cli\n", "ui/cli.py": ""})
    violation = ac.check(root, TOY_RULES)[0][0]
    assert violation.file == "shop/domain/item.py" and violation.line == 3
    assert "domain -> ui (заборонено: залежність угору)" in violation.message


@pytest.mark.parametrize("statement", ["import shop.ui.cli", "from shop.ui import cli",
                                       "from shop.ui.cli import x", "from ..ui import cli"])
def test_every_import_form_is_detected(tmp_path, statement):
    root = make_package(tmp_path, {"domain/item.py": statement + "\n", "ui/cli.py": "x = 1\n"})
    assert any("domain -> ui" in m for m in messages(root))


def test_relative_import_from_package_init(tmp_path):
    root = make_package(tmp_path, {"domain/__init__.py": "from ..ui import cli\n", "ui/cli.py": ""})
    assert any("domain -> ui" in m for m in messages(root))


def test_import_inside_function_is_detected(tmp_path):
    root = make_package(tmp_path, {"domain/item.py": "def f():\n    import shop.ui.cli\n", "ui/cli.py": ""})
    assert any("domain -> ui" in m for m in messages(root))


def test_forbidden_third_party_module(tmp_path):
    root = make_package(tmp_path, {"domain/item.py": "import sqlite3\n"})
    assert any("заборонений модуль sqlite3" in m for m in messages(root))


def test_same_layer_import_is_allowed(tmp_path):
    root = make_package(tmp_path, {"domain/a.py": "from shop.domain import b\n", "domain/b.py": ""})
    assert messages(root) == []


def test_cycle_is_found():
    assert ac.find_cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}}) == [["a", "b", "c", "a"]]


def test_no_cycle_in_diamond():
    assert ac.find_cycles({"a": {"b", "c"}, "b": {"d"}, "c": {"d"}}) == []


def test_statistics_count_distinct_packages():
    graph = {"ui": {"controllers"}, "controllers": {"domain"}}
    stats = ac.package_statistics(graph, ["ui", "controllers", "domain"])
    assert stats == {"ui": (0, 1), "controllers": (1, 1), "domain": (1, 0)}


def test_actual_diagram_shows_real_dependencies():
    text = ac.build_actual_diagram({"ui": {"domain"}}, ["ui", "domain"])
    assert "ui ..> domain" in text and text.startswith("@startuml actual_packages")


def test_compare_with_rules():
    extra, unused = ac.compare_with_rules({"ui": {"foundation"}}, {"allowed": {"ui": ["domain"]}})
    assert extra == ["ui -> foundation"] and unused == ["ui -> domain"]
