from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def normalize_text(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def id_sort_key(req_id: str) -> tuple:
    parts = re.findall(r"[A-Za-zА-Яа-я]+|\d+", req_id)
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts)


@dataclass
class Requirement:
    id: str
    type: str
    text: str
    source: str = ""
    priority: Any = None
    parent: str | None = None
    subsystem: str = ""


@dataclass
class UserStory:
    id: str
    text: str


@dataclass
class SystemRequest:
    sponsor: str = ""
    business_need: str = ""
    business_requirements: list[str] = field(default_factory=list)
    business_value: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class Specification:
    project: str
    system_request: SystemRequest
    stakeholders: list[str]
    user_stories: list[UserStory]
    requirements: list[Requirement]

    def by_type(self, req_type: str) -> list[Requirement]:
        return [r for r in self.requirements if r.type == req_type]

    def children(self, parent_id: str) -> list[Requirement]:
        found = [r for r in self.requirements if r.parent == parent_id]
        return sorted(found, key=lambda r: id_sort_key(r.id))


def _load_requirement(raw: dict) -> Requirement:
    parent = raw.get("parent")
    return Requirement(
        id=normalize_text(raw.get("id")),
        type=normalize_text(raw.get("type")),
        text=normalize_text(raw.get("text")),
        source=normalize_text(raw.get("source")),
        priority=raw.get("priority"),
        parent=normalize_text(parent) if parent is not None else None,
        subsystem=normalize_text(raw.get("subsystem")),
    )


def spec_from_dict(data: dict) -> Specification:
    request = data.get("system_request") or {}
    return Specification(
        project=normalize_text(data.get("project")),
        system_request=SystemRequest(
            sponsor=normalize_text(request.get("sponsor")),
            business_need=normalize_text(request.get("business_need")),
            business_requirements=[normalize_text(x) for x in request.get("business_requirements") or []],
            business_value=[normalize_text(x) for x in request.get("business_value") or []],
            constraints=[normalize_text(x) for x in request.get("constraints") or []],
        ),
        stakeholders=[normalize_text(x) for x in data.get("stakeholders") or []],
        user_stories=[
            UserStory(normalize_text(s.get("id")), normalize_text(s.get("text")))
            for s in data.get("user_stories") or []
        ],
        requirements=[_load_requirement(r) for r in data.get("requirements") or []],
    )


def load_spec(path: str | Path) -> Specification:
    with open(path, encoding="utf-8") as stream:
        return spec_from_dict(yaml.safe_load(stream) or {})
