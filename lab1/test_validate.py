from pathlib import Path

import pytest

import srs_report
import validate as v
from srs_model import Requirement, Specification, SystemRequest, UserStory, load_spec

HERE = Path(__file__).parent


def make_spec(*requirements, stories=()):
    return Specification("Тест", SystemRequest(), [], list(stories), list(requirements))


def req(req_id="R1", text="ІС повинна зберігати дані про препарат.", req_type="functional",
        priority=1, parent=None, source="US-01"):
    return Requirement(req_id, req_type, text, source, priority, parent)


def kinds(defects):
    return {d.kind for d in defects}


@pytest.mark.parametrize("bad_id", ["REQ-1", "R", "R1.", "1", "X1", "N1.1"])
def test_check1_id_format(bad_id):
    assert "формат" in kinds(v.check_ids(make_spec(req(bad_id))))


@pytest.mark.parametrize("good_id", ["R1", "R1.1", "R1.2.3", "N1", "C12"])
def test_check1_valid_id_format(good_id):
    assert v.check_ids(make_spec(req(good_id))) == []


def test_check1_duplicate_id():
    assert "надлишковість" in kinds(v.check_ids(make_spec(req("R1"), req("R1"))))


def test_check2_type():
    assert "формат" in kinds(v.check_types(make_spec(req(req_type="magic"))))


@pytest.mark.parametrize("text", ["ІС ПОВИННА   робити це.", "Система повинна робити це."])
def test_check3_allowed_openings_ignore_case_and_spaces(text):
    assert v.check_wording(make_spec(req(text=text))) == []


def test_check3_wording():
    assert "формулювання" in kinds(v.check_wording(make_spec(req(text="Покупець шукає препарат."))))


@pytest.mark.parametrize("word", ["швидко", "зручний", "легкий", "тощо", "ефективно", "оптимальний",
                                  "інтуїтивний", "гнучкий"])
def test_check4_vague_words(word):
    text = f"ІС повинна робити це {word}."
    assert "неоднозначність" in kinds(v.check_vague_words(make_spec(req(text=text))))


def test_check4_stem_only_at_word_start():
    assert v.check_vague_words(make_spec(req(text="ІС повинна блокувати незручний запит."))) == []


def test_check5_performance_needs_number():
    bad = req("N1", "ІС повинна витримувати навантаження.", "performance")
    good = req("N2", "ІС повинна відповідати за 2 с.", "performance")
    assert [d.req_id for d in v.check_measurable(make_spec(bad, good))] == ["N1"]


@pytest.mark.parametrize("priority", [0, 6, None, "1", True, 1.5])
def test_check6_invalid_priority(priority):
    assert "пріоритет" in kinds(v.check_priorities(make_spec(req(priority=priority))))


@pytest.mark.parametrize("priority", [1, 5])
def test_check6_valid_priority(priority):
    assert v.check_priorities(make_spec(req(priority=priority))) == []


def test_check6_constraint_needs_no_priority():
    assert v.check_priorities(make_spec(req("C1", req_type="constraint", priority=None))) == []


def test_check7_missing_parent():
    defects = v.check_parents(make_spec(req("R2.1", parent="R3")))
    assert "немає батька R3" in defects[0].message


def test_check7_id_must_continue_parent():
    defects = v.check_parents(make_spec(req("R1"), req("R5.1", parent="R1")))
    assert "не продовжує" in defects[0].message


def test_check7_dotted_id_without_parent():
    assert "нетрасованість" in kinds(v.check_parents(make_spec(req("R6.1"))))


def test_check7_valid_hierarchy():
    assert v.check_parents(make_spec(req("R1"), req("R1.1", parent="R1"))) == []


def test_check8_similar_texts():
    first = req("R1", "ІС повинна дозволяти фармацевту продавати препарат.")
    second = req("R2", "ІС повинна дозволяти фармацевту продавати препарати.")
    defects = v.check_similar(make_spec(first, second))
    assert defects[0].req_id == "R2" and "схожа на R1" in defects[0].message


def test_check8_ignores_case_and_spaces():
    first = req("R1", "ІС ПОВИННА зберігати  партії.")
    second = req("R2", "іс повинна зберігати партії.")
    assert "100%" in v.check_similar(make_spec(first, second))[0].message


def test_check8_different_texts():
    first = req("R1", "ІС повинна зберігати партії.")
    second = req("R2", "ІС повинна надсилати сповіщення покупцям про готовність замовлення.")
    assert v.check_similar(make_spec(first, second)) == []


@pytest.mark.parametrize("text", ["ІС повинна мати кнопку.", "ІС повинна показати це на сторінці.",
                                  "ІС повинна писати в таблицю.", "ІС повинна працювати з MySQL."])
def test_check9_implementation_words(text):
    assert "деталі реалізації" in kinds(v.check_implementation_words(make_spec(req(text=text))))


def test_check9_constraint_may_name_technology():
    constraint = req("C1", "ІС повинна використовувати MySQL.", "constraint", None)
    assert v.check_implementation_words(make_spec(constraint)) == []


def test_check10_user_story_coverage():
    stories = [UserStory("US-01", "..."), UserStory("US-02", "...")]
    defects = v.check_user_story_coverage(make_spec(req(source="US-01"), stories=stories))
    assert [d.req_id for d in defects] == ["US-02"]


def test_check11_prefix_must_match_type():
    assert "формат" in kinds(v.check_id_prefix_matches_type(make_spec(req("R1", req_type="security"))))


def test_check11_constraint_has_no_priority():
    constraint = req("C1", req_type="constraint", priority=1)
    assert "пріоритет" in kinds(v.check_id_prefix_matches_type(make_spec(constraint)))


def test_check12_source_required():
    assert "нетрасованість" in kinds(v.check_sources(make_spec(req(source=""))))


def test_check13_regulated_priority():
    low = req(text="ІС повинна перевіряти рецепт.", priority=3)
    high = req("R2", "ІС повинна перевіряти рецепт покупця.", priority=2)
    assert [d.req_id for d in v.check_regulated_priority(make_spec(low, high))] == ["R1"]


def test_working_spec_is_clean():
    assert v.validate(load_spec(HERE / "srs.yaml")) == []


def test_working_spec_meets_lab_minimums():
    spec = load_spec(HERE / "srs.yaml")
    functional = spec.by_type("functional")
    non_functional = [r for r in spec.requirements if r.id.startswith("N")]
    assert len(spec.requirements) >= 15 and len(functional) >= 10
    assert len({r.parent for r in functional if r.parent}) >= 2
    assert len(non_functional) >= 4 and len({r.type for r in non_functional}) >= 3
    assert spec.by_type("constraint")


def test_bad_spec_triggers_every_check():
    spec = load_spec(HERE / "bad_srs.yaml")
    for check in v.CHECKS:
        assert check(spec), f"{check.__name__} не спрацювала на bad_srs.yaml"


def test_exit_codes(capsys):
    assert v.main(["validate.py", str(HERE / "srs.yaml")]) == 0
    assert v.main(["validate.py", str(HERE / "bad_srs.yaml")]) == 1
    assert "знайдено" in capsys.readouterr().out


def test_multiline_text_is_normalized():
    spec = load_spec(HERE / "srs.yaml")
    assert all("\n" not in r.text and "  " not in r.text for r in spec.requirements)


def test_report_structure():
    report = srs_report.build_report(load_spec(HERE / "srs.yaml"))
    assert "## 1. Вступ" in report and "## 2. Загальний опис" in report
    assert "## 3. Специфічні вимоги" in report and "## 4. Статистика вимог" in report
    assert "  - **R2.1** *(пріоритет 1)*" in report
