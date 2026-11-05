"""Сумісний імпорт для коду лабораторних робіт."""

from pharmacy.controllers.sales.common import SaleResult
from pharmacy.controllers.sales.prescription_sale_controller import PrescriptionSaleController

__all__ = ["PrescriptionSaleController", "SaleResult"]
