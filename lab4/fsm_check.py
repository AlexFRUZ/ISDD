"""Перевірка машини станів за таблицею переходів (ЛР 4, завдання 3).

Формат таблиці: state;event;guard;action;next. Рядок зі станом [*] задає початковий
стан, рядок із next=[*] робить стан кінцевим. Порожній next означає, що подію
оголошено, але цей стан її не приймає (клітинка NA).

Запуск: python fsm_check.py transitions.csv --name reservation_states
Код завершення: 0 - аномалій немає, 1 - аномалії знайдено.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

PSEUDO_STATE = "[*]"


@dataclass(frozen=True)
class Transition:
    state: str
    event: str
    guard: str
    action: str
    next: str


def load_transitions(path: str | Path) -> list[Transition]:
    with open(path, encoding="utf-8", newline="") as stream:
        return [Transition(**{k: (v or "").strip() for k, v in rec.items()})
                for rec in csv.DictReader(stream, delimiter=";")]


class StateMachine:
    def __init__(self, transitions: list[Transition]) -> None:
        self.rows = transitions
        self.real = [t for t in transitions if t.next]

    @property
    def states(self) -> list[str]:
        names = [n for t in self.rows for n in (t.state, t.next)]
        return list(dict.fromkeys(n for n in names if n and n != PSEUDO_STATE))

    @property
    def events(self) -> list[str]:
        return list(dict.fromkeys(t.event for t in self.rows))

    @property
    def initial_states(self) -> list[str]:
        return [t.next for t in self.real if t.state == PSEUDO_STATE]

    @property
    def final_states(self) -> list[str]:
        return list(dict.fromkeys(t.state for t in self.real if t.next == PSEUDO_STATE))

    def dead_states(self) -> list[str]:
        """Стан без вихідних переходів, який не є кінцевим (порожній рядок таблиці)."""
        with_exit = {t.state for t in self.real}
        return [s for s in self.states if s not in with_exit]

    def unreachable_states(self) -> list[str]:
        """Обхід графа в ширину від початкового стану."""
        graph: dict[str, set[str]] = defaultdict(set)
        for transition in self.real:
            graph[transition.state].add(transition.next)
        visited = set(self.initial_states)
        queue = deque(visited)
        while queue:
            for neighbour in graph[queue.popleft()]:
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(neighbour)
        return [s for s in self.states if s not in visited]

    def neglected_events(self) -> list[str]:
        """Подія, яку не приймає жоден стан (порожній стовпець таблиці)."""
        accepted = {t.event for t in self.real}
        return [e for e in self.events if e not in accepted]

    def nondeterminism(self) -> list[str]:
        """Кілька переходів за однією подією з однаковою умовою, зокрема без умови."""
        groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for transition in self.real:
            groups[(transition.state, transition.event, transition.guard)].append(transition.next)
        return [f"({state}, {event}) -> {' | '.join(targets)}"
                for (state, event, _), targets in groups.items() if len(targets) > 1]

    def to_plantuml(self, title: str) -> str:
        alias = {name: f"S{i}" for i, name in enumerate(self.states, start=1)}
        alias[PSEUDO_STATE] = PSEUDO_STATE
        lines = [f"@startuml {title}", f"title Машина станів: {title}", "hide empty description", ""]
        lines += [f'state "{name}" as {alias[name]}' for name in self.states]
        lines.append("")
        for transition in self.real:
            label = transition.event
            if transition.guard:
                label += f" [{transition.guard}]"
            if transition.action:
                label += f" / {transition.action}"
            lines.append(f"{alias[transition.state]} --> {alias[transition.next]} : {label}")
        return "\n".join(lines + ["@enduml", ""])

    def to_markdown(self) -> str:
        """Таблиця «стани x події»: клітинка містить наступний стан, умову й дію."""
        cells: dict[tuple[str, str], list[str]] = defaultdict(list)
        for transition in self.real:
            text = "кінець" if transition.next == PSEUDO_STATE else transition.next
            if transition.guard:
                text += f" [{transition.guard}]"
            if transition.action:
                text += f" / {transition.action}"
            cells[(transition.state, transition.event)].append(text)
        events = [e for e in self.events if e != "створити"]
        lines = ["# Таблиця переходів станів", "", "| Стан \\ подія | " + " | ".join(events) + " |",
                 "|---|" + "---|" * len(events)]
        for state in self.states:
            row = ["<br>".join(cells.get((state, e), ["NA"])) for e in events]
            lines.append(f"| {state} | " + " | ".join(row) + " |")
        return "\n".join(lines) + "\n"


def _names(items: list[str]) -> str:
    return ", ".join(items) if items else "немає"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Перевірка таблиці переходів")
    parser.add_argument("table")
    parser.add_argument("--name", default="reservation_states")
    args = parser.parse_args(argv)

    machine = StateMachine(load_transitions(args.table))
    print(f"Станів: {len(machine.states)}, подій: {len(machine.events)}, переходів: {len(machine.real)}")
    print("Початковий стан:", _names(machine.initial_states))
    print("Кінцеві стани:", _names(machine.final_states))
    found = {
        "Тупикові стани": machine.dead_states(),
        "Недосяжні стани": machine.unreachable_states(),
        "Знехтувані події": machine.neglected_events(),
        "Недетермінованість": machine.nondeterminism(),
    }
    for title, items in found.items():
        print(f"{title}: {_names(items)}")
    Path(f"{args.name}.puml").write_text(machine.to_plantuml(args.name), encoding="utf-8")
    Path(f"{args.name}.md").write_text(machine.to_markdown(), encoding="utf-8")
    print(f"Збережено: {args.name}.puml, {args.name}.md")
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
