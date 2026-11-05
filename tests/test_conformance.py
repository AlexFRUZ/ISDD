import dataclasses
import sys
from pathlib import Path

import pytest
import yaml

import pharmacy.domain as domain

LAB2 = Path(__file__).resolve().parent.parent / "lab2"
sys.path.insert(0, str(LAB2))
from classification_io import class_names, load_rows

ROWS = load_rows(LAB2 / "classification.csv")
with open(LAB2 / "name_map.yaml", encoding="utf-8") as stream:
    NAME_MAP = yaml.safe_load(stream)
CLASS_MAP = NAME_MAP["classes"]
ATTRIBUTE_MAP = NAME_MAP["attributes"]


def python_class(model_name):
    return getattr(domain, CLASS_MAP[model_name])


def field_names(cls):
    return {f.name for f in dataclasses.fields(cls)}


@pytest.mark.parametrize("name", class_names(ROWS))
def test_class_exists(name):
    assert name in CLASS_MAP, f"немає зіставлення для класу «{name}»"
    assert hasattr(domain, CLASS_MAP[name]), f"у коді немає класу {CLASS_MAP[name]}"


@pytest.mark.parametrize(
    "owner, attribute",
    [(r.owner, r.attribute_name) for r in ROWS if r.code == "A"],
)
def test_attribute_exists(owner, attribute):
    python_name = ATTRIBUTE_MAP[owner][attribute]
    assert python_name in field_names(python_class(owner)), \
        f"{CLASS_MAP[owner]} не має поля {python_name} для атрибута «{attribute}»"


@pytest.mark.parametrize("parent, child", [(r.owner, r.target) for r in ROWS if r.code == "I"])
def test_inheritance(parent, child):
    assert issubclass(python_class(child), python_class(parent)), \
        f"{CLASS_MAP[child]} має успадковувати {CLASS_MAP[parent]}"


@pytest.mark.parametrize("row", [r for r in ROWS if r.code == "AC"], ids=lambda r: r.name)
def test_association_class_links_both_ends(row):
    fields = {f.name: f.type for f in dataclasses.fields(python_class(row.name))}
    assert CLASS_MAP[row.owner] in fields.values() and CLASS_MAP[row.target] in fields.values()


@pytest.mark.parametrize(
    "owner, target",
    [(r.owner, r.target) for r in ROWS if r.code in ("AS", "AG")],
)
def test_relation_has_reference_in_code(owner, target):
    def refers(source, destination):
        return any(CLASS_MAP[destination] in str(f.type) for f in dataclasses.fields(python_class(source)))
    assert refers(owner, target) or refers(target, owner), f"немає зв'язку {owner} – {target}"


def test_model_meets_lab_minimums():
    codes = [r.code for r in ROWS]
    assert len(class_names(ROWS)) >= 8 and codes.count("A") >= 20
    assert sum(codes.count(c) for c in ("AS", "AG", "I", "AC")) >= 6
    assert "AS" in codes and "AC" in codes and ("AG" in codes or "I" in codes)
