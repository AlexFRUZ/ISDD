"""Джерело поточного часу. Контролери отримують його явно, щоб тести були детермінованими."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now()
