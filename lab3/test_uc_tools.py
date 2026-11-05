import copy
import importlib.util
from pathlib import Path

import pytest

import ucd

HERE = Path(__file__).parent

_spec = importlib.util.spec_from_file_location("trace_tool", HERE / "trace.py")
trace = importlib.util.module_from_spec(_spec)
import sys

sys.modules["trace_tool"] = trace
_spec.loader.exec_module(trace)


@pytest.fixture
def model():
    return ucd.load_model(HERE / "use_cases.yaml")


def req(req_id, priority=1, req_type="functional"):
    return {"id": req_id, "priority": priority, "type": req_type}


def uc(uc_id, requirements, effort=1, depends_on=(), include=()):
    return {"id": uc_id, "requirements": list(requirements), "effort": effort,
            "depends_on": list(depends_on), "include": list(include)}


def test_real_model_is_clean_and_meets_minimums(model):
    assert ucd.check_model(model) == []
    assert len(model["use_cases"]) >= 8 and len(model["actors"]) >= 3
    assert any(a["kind"] == "system" for a in model["actors"]) and len(model["subsystems"]) >= 2


def test_check_single_word_name(model):
    model["use_cases"][0]["name"] = "Пошук"
    assert any("дієслово + іменник" in r for r in ucd.check_model(model))


def test_check_missing_actor_and_requirement(model):
    model["use_cases"][0]["actors"] = []
    model["use_cases"][0]["requirements"] = []
    remarks = ucd.check_model(model)
    assert any("немає актора" in r for r in remarks) and any("немає пов'язаної" in r for r in remarks)


def test_check_unknown_include(model):
    model["use_cases"][0]["include"] = ["UC99"]
    assert any("неіснуючий UC99" in r for r in ucd.check_model(model))


def test_check_too_many_use_cases_in_subsystem(model):
    source = model["use_cases"][0]
    model["use_cases"] += [dict(copy.deepcopy(source), id=f"UC{n}") for n in range(20, 28)]
    assert any("> 8" in r for r in ucd.check_model(model))


def test_check_isolated_actor(model):
    model["actors"].append({"name": "Бухгалтер", "kind": "human"})
    assert any("«Бухгалтер» ізольований" in r for r in ucd.check_model(model))


def test_diagram_has_all_elements(model):
    text = ucd.build_diagram(model, "Резервування")
    assert 'rectangle "Резервування"' in text and "<<extend>>" in text and "<<include>>" in text
    assert 'usecase "UC9 Перевірити е-рецепт" as UC9' in text
    assert "<|--" in text


def test_uc_priority_is_highest_of_linked_requirements():
    matrix = trace.Matrix([req("R1", 3), req("R2", 1)], [uc("UC1", ["R1", "R2"])])
    assert matrix.uc_priority(matrix.use_cases[0]) == 1


def test_empty_rows_columns_and_unknown_references():
    matrix = trace.Matrix(
        [req("R1"), req("R2"), req("N1", 2, "performance")],
        [uc("UC1", ["R1"]), uc("UC2", []), uc("UC3", ["R9"])],
    )
    assert [r["id"] for r in matrix.empty_rows()] == ["R2", "N1"]
    assert [r["id"] for r in matrix.empty_rows(functional_only=True)] == ["R2"]
    assert matrix.empty_columns() == ["UC2", "UC3"]
    assert matrix.unknown_references() == [("UC3", "R9")]


def test_plan_respects_priority_and_capacity():
    matrix = trace.Matrix([req("R1", 1), req("R2", 2)], [uc("UC2", ["R2"], 4), uc("UC1", ["R1"], 4)])
    plan, left = trace.plan_iterations(matrix, capacity=5, iterations=2)
    assert [[u["id"] for u in it] for it in plan] == [["UC1"], ["UC2"]] and left == {}


def test_plan_never_places_use_case_before_dependency():
    matrix = trace.Matrix(
        [req("R1", 1), req("R2", 2)],
        [uc("UC1", ["R1"], 1, depends_on=["UC2"]), uc("UC2", ["R2"], 1)],
    )
    plan, _ = trace.plan_iterations(matrix, capacity=5, iterations=1)
    assert [u["id"] for u in plan[0]] == ["UC2", "UC1"]


def test_plan_treats_include_as_dependency():
    matrix = trace.Matrix(
        [req("R1", 1), req("R2", 2)],
        [uc("UC1", ["R1"], 3, include=["UC2"]), uc("UC2", ["R2"], 3)],
    )
    plan, _ = trace.plan_iterations(matrix, capacity=3, iterations=2)
    assert [[u["id"] for u in it] for it in plan] == [["UC2"], ["UC1"]]


def test_plan_reports_what_does_not_fit():
    matrix = trace.Matrix(
        [req("R1")],
        [uc("UC1", ["R1"], 20), uc("UC2", ["R1"], 1, depends_on=["UC1"])],
    )
    _, left = trace.plan_iterations(matrix, capacity=10, iterations=2)
    assert left == {"UC1": "бракує потужності", "UC2": "залежність не розподілено"}


def test_find_tests_reads_markers():
    found = trace.find_tests(HERE)
    assert "test_flow_4a_quantity_above_prescribed" in found["R6.3"]
    assert "test_flow_3b_recipe_invalid" in found["R6.2"]
