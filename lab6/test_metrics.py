"""Тести metrics.py і відповідності діаграми класів проєкту коду (ЛР 6)."""
import importlib
import re
import sys
from pathlib import Path

import pytest

import metrics as m

HERE = Path(__file__).parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))


def analyse(tmp_path, source):
    (tmp_path / "pkg").mkdir(exist_ok=True)
    (tmp_path / "pkg" / "code.py").write_text(source, encoding="utf-8")
    return m.compute_metrics(m.collect_classes(tmp_path / "pkg"))


def test_counts_methods_and_attributes(tmp_path):
    classes = analyse(tmp_path, """
class A:
    x: int
    def __init__(self):
        self.y = 1
    def first(self): pass
    def second(self): pass
""")
    assert classes["A"].methods == 2 and classes["A"].attributes == 2


def test_dit_counts_project_parents_only(tmp_path):
    classes = analyse(tmp_path, """
class A(Exception): pass
class B(A): pass
class C(B): pass
""")
    assert (classes["A"].dit, classes["B"].dit, classes["C"].dit) == (0, 1, 2)


def test_fan_out_and_fan_in(tmp_path):
    classes = analyse(tmp_path, """
class A: pass
class B: pass
class C:
    a: A
    def make(self) -> "B":
        return B()
""")
    assert classes["C"].fan_out == 2
    assert classes["A"].fan_in == 1 and classes["B"].fan_in == 1 and classes["C"].fan_in == 0


def test_decision_points(tmp_path):
    classes = analyse(tmp_path, """
class A:
    def check(self, items):
        if items and len(items) > 1:
            return [x for x in items if x]
        for item in items:
            pass
""")
    assert classes["A"].decisions == 5  # if, and, comprehension, if у comprehension, for


def test_class_does_not_count_itself(tmp_path):
    classes = analyse(tmp_path, "class A:\n    def clone(self):\n        return A()\n")
    assert classes["A"].fan_out == 0


@pytest.mark.parametrize("attribute, value, text", [
    ("methods", 11, "методів 11"), ("fan_out", 6, "fan-out 6"), ("dit", 4, "DIT 4"),
])
def test_warnings(attribute, value, text):
    info = m.ClassInfo("A", "code")
    setattr(info, attribute, value)
    assert text in m.warnings({"A": info}, 10, 5, 3)[0]


def test_no_warning_at_threshold():
    assert m.warnings({"A": m.ClassInfo("A", "code", methods=10, fan_out=5, dit=3)}, 10, 5, 3) == []


def dcd_classes():
    """Методи кожного класу з dcd.puml: рядки виду +назва(...)."""
    text = (HERE / "diagrams" / "dcd.puml").read_text(encoding="utf-8")
    for match in re.finditer(r"class (\w+)[^\n]*\{\n(.*?)\n\}", text, re.S):
        yield match.group(1), re.findall(r"\+(\w+)\(", match.group(2))


MODULES = ["pharmacy.domain", "pharmacy.persistence.store", "pharmacy.network.registry",
           "pharmacy.controllers.prescription_sale_controller",
           "pharmacy.controllers.reservation_controller"]


def find_class(name):
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        if hasattr(module, name):
            return getattr(module, name)
    raise AssertionError(f"у коді немає класу {name}")


@pytest.mark.parametrize("class_name, methods", list(dcd_classes()), ids=lambda v: str(v))
def test_dcd_matches_code(class_name, methods):
    cls = find_class(class_name)
    missing = [name for name in methods if not hasattr(cls, name)]
    assert not missing, f"{class_name} не має методів {missing}"
