"""Генератор діаграм варіантів використання та перевірка моделі (ЛР 3, завдання 1).

Запуск: python ucd.py use_cases.yaml -o diagrams
Код завершення: 0 - модель без зауважень, 1 - зауваження є, 2 - помилка запуску.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

MAX_USE_CASES_PER_SUBSYSTEM = 8


def load_model(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as stream:
        model = yaml.safe_load(stream)
    for use_case in model["use_cases"]:
        for key in ("actors", "requirements", "include", "extend", "depends_on"):
            use_case.setdefault(key, [])
    return model


def check_model(model: dict) -> list[str]:
    """Перевірки якості з пункту 5 завдання 1."""
    use_cases = model["use_cases"]
    ids = {uc["id"] for uc in use_cases}
    remarks: list[str] = []
    for uc in use_cases:
        if len(uc["name"].split()) < 2:
            remarks.append(f"{uc['id']}: назва «{uc['name']}» не має форми «дієслово + іменник»")
        if not uc["actors"]:
            remarks.append(f"{uc['id']}: немає актора")
        if not uc["requirements"]:
            remarks.append(f"{uc['id']}: немає пов'язаної вимоги")
        for kind in ("include", "extend"):
            for ref in uc[kind]:
                if ref not in ids:
                    remarks.append(f"{uc['id']}: {kind} посилається на неіснуючий {ref}")
    for subsystem in model["subsystems"]:
        count = sum(uc["subsystem"] == subsystem for uc in use_cases)
        if count > MAX_USE_CASES_PER_SUBSYSTEM:
            remarks.append(f"Підсистема «{subsystem}»: {count} use cases (> {MAX_USE_CASES_PER_SUBSYSTEM})")
    used = {name for uc in use_cases for name in uc["actors"]}
    parents = {a.get("parent") for a in model["actors"] if a["name"] in used}
    remarks += [
        f"Актор «{a['name']}» ізольований"
        for a in model["actors"]
        if a["name"] not in used and a["name"] not in parents and a.get("parent") not in used
    ]
    return remarks


def _actors_for(model: dict, own_use_cases: list[dict]) -> list[dict]:
    """Актори підсистеми разом із батьками, щоб показати узагальнення."""
    direct = {name for uc in own_use_cases for name in uc["actors"]}
    by_name = {a["name"]: a for a in model["actors"]}
    names = set(direct)
    for name in direct:
        while by_name[name].get("parent"):
            name = by_name[name]["parent"]
            names.add(name)
    # Дочірні актори успадковують асоціації батька, якщо він пов'язаний із цією підсистемою.
    names |= {a["name"] for a in model["actors"] if a.get("parent") in direct}
    return [a for a in model["actors"] if a["name"] in names]


def build_diagram(model: dict, subsystem: str) -> str:
    use_cases = {uc["id"]: uc for uc in model["use_cases"]}
    own = [uc for uc in model["use_cases"] if uc["subsystem"] == subsystem]
    own_ids = {uc["id"] for uc in own}
    actors = _actors_for(model, own)
    alias = {a["name"]: f"A{i}" for i, a in enumerate(actors, start=1)}

    lines = [f"@startuml uc_{model['subsystems'][subsystem]}",
             f"title Діаграма варіантів використання: підсистема «{subsystem}»",
             "left to right direction", "skinparam packageStyle rectangle", ""]
    for actor in actors:
        stereotype = " <<система>>" if actor["kind"] == "system" else ""
        lines.append(f'actor "{actor["name"]}" as {alias[actor["name"]]}{stereotype}')
    lines += ["", f'rectangle "{subsystem}" {{']
    lines += [f'  usecase "{uc["id"]} {uc["name"]}" as {uc["id"]}' for uc in own]
    lines += ["}", ""]

    # Варіанти використання інших підсистем показуємо поза межею, якщо на них є посилання.
    foreign = sorted({ref for uc in own for kind in ("include", "extend") for ref in uc[kind]} - own_ids)
    lines += [f'usecase "{ref} {use_cases[ref]["name"]}" as {ref}' for ref in foreign]

    for actor in actors:
        if actor.get("parent"):
            lines.append(f'{alias[actor["parent"]]} <|-- {alias[actor["name"]]}')
    for uc in own:
        lines += [f'{alias[name]} -- {uc["id"]}' for name in uc["actors"]]
        lines += [f'{uc["id"]} ..> {ref} : <<include>>' for ref in uc["include"]]
        lines += [f'{uc["id"]} ..> {ref} : <<extend>>' for ref in uc["extend"]]
    return "\n".join(lines + ["@enduml", ""])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Діаграми варіантів використання")
    parser.add_argument("model")
    parser.add_argument("-o", "--output", default="diagrams")
    args = parser.parse_args(argv)
    model = load_model(args.model)
    output = Path(args.output)
    output.mkdir(exist_ok=True)
    for subsystem, slug in model["subsystems"].items():
        path = output / f"uc_{slug}.puml"
        path.write_text(build_diagram(model, subsystem), encoding="utf-8")
        print(f"Збережено: {path}")
    remarks = check_model(model)
    for remark in remarks:
        print(remark)
    print(f"Use cases: {len(model['use_cases'])}, акторів: {len(model['actors'])}, зауважень: {len(remarks)}")
    return 1 if remarks else 0


if __name__ == "__main__":
    sys.exit(main())
