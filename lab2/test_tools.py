from pathlib import Path

import brainstorm as b
import dmcd
import review as r
from classification_io import Row, load_rows

HERE = Path(__file__).parent


def row(code, name, owner="", target="", mult=""):
    return Row("фраза", code, name, owner, target, mult, "", "")


CLASS_A, CLASS_B = row("C", "Аптека"), row("C", "Партія")
ATTR_A = row("A", "адреса : String", "Аптека")
ATTR_B = row("A", "серія : String", "Партія")
LINK = row("AS", "зберігає", "Аптека", "Партія", "1;0..*")


def test_brainstorm_counts_duplicates_ignoring_case_and_spaces():
    phrases = b.collect_phrases("[Аптека]{1} і [аптека]{1} та [ аптека ]{1}")
    assert [(p.text, p.rule, p.count) for p in phrases] == [("аптека", 1, 3)]


def test_brainstorm_merges_inflected_forms_by_canonical_form():
    phrases = b.collect_phrases("[аптек|аптека]{1} [аптека]{1}")
    assert phrases[0].count == 2


def test_brainstorm_keeps_same_phrase_with_different_rules():
    assert len(b.collect_phrases("[має]{6} [має]{8}")) == 2


def test_brainstorm_reports_unclosed_bracket():
    assert "незакрита" in b.find_markup_errors("[аптека{1}")[0]


def test_brainstorm_reports_rule_out_of_range():
    assert "поза діапазоном" in b.find_markup_errors("[аптека]{10}")[0]
    assert "поза діапазоном" in b.find_markup_errors("[аптека]{0}")[0]


def test_brainstorm_reports_missing_rule_number():
    assert "немає номера" in b.find_markup_errors("[аптека] далі текст")[-1]


def test_brainstorm_accepts_real_domain_text():
    text = (HERE / "domain.txt").read_text(encoding="utf-8")
    assert b.find_markup_errors(text) == []


def test_domain_text_has_at_least_300_words():
    text = (HERE / "domain.txt").read_text(encoding="utf-8")
    plain = b.MARKUP.sub(lambda m: m.group(1).split("|")[0], text)
    assert len(plain.split()) >= 300


def test_review_clean_model():
    assert r.review([CLASS_A, CLASS_B, ATTR_A, ATTR_B, LINK]) == []


def test_review_class_without_attributes():
    assert r.check_classes_without_attributes([CLASS_A]) == ["Клас «Аптека» не має атрибутів"]


def test_review_isolated_class():
    assert "ізольований" in r.check_isolated_classes([CLASS_A])[0]


def test_review_missing_multiplicity():
    link = row("AS", "зберігає", "Аптека", "Партія", "1;")
    assert "не має кратностей" in r.check_missing_multiplicities([link])[0]


def test_review_inheritance_needs_no_multiplicity():
    assert r.check_missing_multiplicities([row("I", "є", "Препарат", "Рецептурний препарат")]) == []


def test_review_unknown_class():
    assert "неіснуючий клас «Партія»" in r.check_unknown_classes([CLASS_A, LINK])[0]


def test_review_class_used_as_attribute():
    attribute = row("A", "партія : String", "Аптека")
    assert "збігається з назвою класу" in r.check_class_as_attribute([CLASS_A, CLASS_B, attribute])[0]


def test_review_class_used_as_attribute_type():
    attribute = row("A", "основна : Партія", "Аптека")
    assert r.check_class_as_attribute([CLASS_A, CLASS_B, attribute])


def test_review_duplicate_class():
    assert "визначено 2 рази" in r.check_duplicate_classes([CLASS_A, CLASS_A])[0]


def test_real_classification_has_no_remarks():
    assert r.review(load_rows(HERE / "classification.csv")) == []


def test_diagram_contains_all_relation_kinds_and_no_operations():
    text = dmcd.build_diagram(load_rows(HERE / "classification.csv"), dmcd.load_aliases())
    assert 'class "Аптека" as Pharmacy {' in text
    assert 'Customer "1" -- "0..3" Reservation : створює >' in text
    assert 'PharmacyChain "1" o-- "1..*" Pharmacy : складається з >' in text
    assert "Drug <|-- PrescriptionDrug" in text
    assert "(Sale, Batch) .. SaleLine" in text
    assert "()" not in text
