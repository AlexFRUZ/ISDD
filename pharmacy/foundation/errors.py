from __future__ import annotations

class DomainError(Exception):
    pass


class TransitionError(DomainError):
    pass


class Refused(Exception):
    def __init__(self, flow: str, message: str) -> None:
        super().__init__(message)
        self.flow = flow


class ContractError(DomainError):
    pass
