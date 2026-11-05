from pathlib import Path

import pytest

import crude
import seq_gen as sg
from fsm_check import StateMachine, Transition, load_transitions

HERE = Path(__file__).parent


def msg(no, subject, target, kind="call", action="дія", data=""):
    return sg.Row(str(no), subject, action, data, target, kind)


def fragment(no, kind, text=""):
    return sg.Row(str(no), "", text, "", "", kind)


def t(state, event, next_state, guard="", action=""):
    return Transition(state, event, guard, action, next_state)


@pytest.mark.parametrize("table", ["uc7_sale.csv", "uc2_reserve.csv"])
def test_real_tables_pass_kung_rule(table):
    rows = sg.load_table(HERE / table)
    assert sg.check_kung_rule(rows) == [] and sg.check_fragments(rows) == []


def test_swapped_rows_violate_kung_rule():
    violations = sg.check_kung_rule(sg.load_table(HERE / "uc7_broken.csv"))
    assert len(violations) == 1 and 'суб\'єкт "Реєстр"' in violations[0]


def test_subject_may_be_earlier_subject():
    rows = [msg(1, "A", "B"), msg(2, "B", "C"), msg(3, "A", "D")]
    assert sg.check_kung_rule(rows) == []


def test_fragment_rows_do_not_break_rule():
    rows = [msg(1, "A", "B"), fragment(2, "alt", "умова"), msg(3, "B", "C"), fragment(4, "end")]
    assert sg.check_kung_rule(rows) == []


def test_unclosed_fragment_is_reported():
    assert "не закрито" in sg.check_fragments([fragment(1, "alt")])[0]


def test_extra_end_is_reported():
    assert "end без" in sg.check_fragments([fragment(1, "end")])[0]


def test_else_outside_alt_is_reported():
    assert "else поза" in sg.check_fragments([fragment(1, "loop"), fragment(2, "else")])[0]


def test_participant_kinds_and_order():
    rows = [msg(1, "Фармацевт", "ПродажUI"), msg(2, "ПродажUI", "КонтролерПродажу"),
            msg(3, "КонтролерПродажу", "DBMgr")]
    text = sg.build_diagram(rows, "t")
    assert 'actor "Фармацевт"' in text and 'boundary "ПродажUI"' in text
    assert 'control "КонтролерПродажу"' in text and 'participant "DBMgr"' in text
    assert sg.participants(rows) == ["Фармацевт", "ПродажUI", "КонтролерПродажу", "DBMgr"]


def test_message_styles():
    rows = [msg(1, "A", "B", action="дія", data="x"), msg(2, "B", "A", "return", "результат"),
            msg(3, "A", "C", "create", "створює")]
    text = sg.build_diagram(rows, "t")
    assert "P1 -> P2 : дія(x)" in text and "P2 --> P1 : результат()" in text
    assert 'create participant "C" as P3' in text


def test_broken_table_returns_error_code(capsys):
    assert sg.main([str(HERE / "uc7_broken.csv")]) == 1
    assert "Знайдено порушень: 1" in capsys.readouterr().out


KEYWORDS = {"R": ["отримує"], "U": ["змінює"], "D": ["видаляє"]}


@pytest.mark.parametrize("action, kind, letter", [
    ("створює", "create", "C"), ("отримує дані", "call", "R"), ("змінює дані", "call", "U"),
    ("видаляє запис", "call", "D"), ("передає запит", "call", "E"),
])
def test_letters(action, kind, letter):
    assert crude.letter_for(msg(1, "A", "B", kind, action), KEYWORDS) == letter


def test_matrix_skips_actor_and_returns():
    rows = [msg(1, "Актор", "UI"), msg(2, "UI", "K", action="отримує"), msg(3, "K", "UI", "return")]
    matrix = crude.build_matrix([rows], KEYWORDS)
    assert list(matrix) == ["UI"] and matrix["UI"]["K"] == {"R"}


def test_coupling_counts():
    matrix = {"A": {"B": {"R"}, "C": {"E"}}, "B": {"C": {"U"}}}
    assert crude.coupling(matrix) == {"A": (2, 0), "B": (1, 1), "C": (0, 2)}


def test_created_but_never_read():
    assert crude.created_but_never_read({"A": {"B": {"C"}, "D": {"C", "R"}}}) == ["B"]


def test_links_missing_in_domain():
    matrix = {"Продаж": {"Партія": {"U"}, "Лікар": {"R"}}}
    missing = crude.links_missing_in_domain(
        matrix, {"Продаж", "Партія", "Лікар"}, {frozenset(("Продаж", "Партія"))})
    assert missing == ["Продаж -> Лікар"]


GOOD = [t("[*]", "почати", "A"), t("A", "далі", "B"), t("B", "кінець", "[*]")]


def test_clean_machine_has_no_anomalies():
    machine = StateMachine(GOOD)
    assert not (machine.dead_states() or machine.unreachable_states()
                or machine.neglected_events() or machine.nondeterminism())


def test_real_table_is_clean_and_meets_minimums():
    machine = StateMachine(load_transitions(HERE / "transitions.csv"))
    assert not (machine.dead_states() or machine.unreachable_states()
                or machine.neglected_events() or machine.nondeterminism())
    assert len(machine.states) >= 5 and len(machine.events) >= 6


def test_broken_table_has_all_four_anomalies():
    machine = StateMachine(load_transitions(HERE / "transitions_broken.csv"))
    assert machine.dead_states() == ["Карантин"]
    assert machine.unreachable_states() == ["Архівне"]
    assert machine.neglected_events() == ["перенести"]
    assert machine.nondeterminism() == ["(Готове, скасувати) -> Скасоване | Прострочене"]


def test_dead_state():
    assert StateMachine([*GOOD, t("A", "у тупик", "C")]).dead_states() == ["C"]


def test_final_state_is_not_dead():
    assert "B" not in StateMachine(GOOD).dead_states()


def test_unreachable_state():
    assert StateMachine([*GOOD, t("Z", "кінець", "[*]")]).unreachable_states() == ["Z"]


def test_neglected_event():
    assert StateMachine([*GOOD, t("A", "забута", "")]).neglected_events() == ["забута"]


def test_nondeterminism_without_guards():
    machine = StateMachine([*GOOD, t("A", "далі", "C"), t("C", "кінець", "[*]")])
    assert machine.nondeterminism() == ["(A, далі) -> B | C"]


def test_different_guards_are_deterministic():
    machine = StateMachine([t("A", "далі", "B", guard="x"), t("A", "далі", "C", guard="не x")])
    assert machine.nondeterminism() == []


def test_markdown_table_marks_empty_cells():
    assert "NA" in StateMachine(GOOD).to_markdown()


def test_diagram_contains_guard_and_action():
    machine = StateMachine([t("[*]", "почати", "A"), t("A", "далі", "[*]", "умова", "дія")])
    assert "S1 --> [*] : далі [умова] / дія" in machine.to_plantuml("t")
