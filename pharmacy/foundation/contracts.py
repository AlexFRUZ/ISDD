from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pharmacy.foundation.errors import ContractError

Method = TypeVar("Method", bound=Callable[..., Any])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(f"Постумову порушено: {message}")


def invariant(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def keeps_invariant(method: Method) -> Method:
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        snapshot = {k: list(v) if isinstance(v, list) else v for k, v in vars(self).items()}
        try:
            result = method(self, *args, **kwargs)
            self.check_invariant()
        except ContractError:
            vars(self).clear()
            vars(self).update(snapshot)
            raise
        return result
    return wrapper
