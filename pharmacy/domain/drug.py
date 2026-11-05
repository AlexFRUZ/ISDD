from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pharmacy.domain.batch import Batch


@dataclass(eq=False)
class Drug:
    trade_name: str
    inn: str
    dosage_form: str
    dosage: str
    manufacturer: str
    batches: list[Batch] = field(default_factory=list, repr=False)

    @property
    def requires_prescription(self) -> bool:
        return False


@dataclass(eq=False)
class PrescriptionDrug(Drug):
    control_group: str = "загальна"

    @property
    def requires_prescription(self) -> bool:
        return True


@dataclass(eq=False)
class OtcDrug(Drug):
    check_limit: int = 10
