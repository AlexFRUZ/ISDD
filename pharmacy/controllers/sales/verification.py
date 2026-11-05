from __future__ import annotations

from datetime import date

from pharmacy.domain import EPrescription
from pharmacy.foundation.errors import Refused
from pharmacy.network.registry import PrescriptionRegistry, RegistryUnavailable


class PrescriptionVerificationService:
    """UC9: єдина точка перевірки та погашення е-рецептів."""

    def __init__(self, registry: PrescriptionRegistry) -> None:
        self.registry = registry

    def verify(self, number: str, today: date) -> EPrescription:
        try:
            recipe = self.registry.find(number)
        except RegistryUnavailable:
            raise Refused("2a", "Реєстр е-рецептів недоступний") from None
        if recipe is None:
            raise Refused("3a", f"Рецепт {number} не знайдено в реєстрі")
        reason = recipe.invalid_reason(today)
        if reason:
            raise Refused("3b", f"Рецепт {number} недійсний: {reason}")
        return recipe

    def verified_for(self, number: str, inn: str, today: date) -> EPrescription:
        """Інтерфейс UC9 для підсистеми «Резервування»."""
        try:
            recipe = self.verify(number, today)
        except Refused:
            raise Refused("6b", f"Рецепт {number} не підходить для цього препарату") from None
        if recipe.inn != inn:
            raise Refused("6b", f"Рецепт {number} не підходить для цього препарату")
        return recipe

    def redeem(self, recipe: EPrescription, quantity: int, today: date) -> None:
        try:
            self.registry.redeem(recipe, quantity, today)
        except RegistryUnavailable:
            raise Refused("6a", "Реєстр е-рецептів недоступний. Продаж не оформлено.") from None
