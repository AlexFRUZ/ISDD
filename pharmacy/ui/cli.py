"""Консольний інтерфейс. Лише розбирає аргументи й друкує результат.

Приклади:
  python -m pharmacy.ui.cli seed
  python -m pharmacy.ui.cli reserve --phone +380671112233 --pharmacy А-01 --drug Парацетамол --qty 2
  python -m pharmacy.ui.cli sell --pharmacist Ф-7 --recipe E-100 --qty 1
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from pharmacy.controllers.factory import build_app, create_demo_data
from pharmacy.foundation.errors import DomainError, Refused

DEFAULT_DATA = "pharmacy_data.pkl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pharmacy", description="ІС «Мережа аптек»")
    parser.add_argument("--data", default=DEFAULT_DATA, help="файл зі станом застосунку")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("seed", help="створити демонстраційні дані")

    reserve = commands.add_parser("reserve", help="UC2 Зарезервувати препарат")
    reserve.add_argument("--phone", required=True)
    reserve.add_argument("--pharmacy", required=True)
    reserve.add_argument("--drug", required=True)
    reserve.add_argument("--qty", type=int, default=1)
    reserve.add_argument("--recipe")

    sell = commands.add_parser("sell", help="UC7 Продати за е-рецептом")
    sell.add_argument("--pharmacist", required=True)
    sell.add_argument("--recipe", required=True)
    sell.add_argument("--qty", type=int, default=1)
    sell.add_argument("--registry-down", action="store_true", help="змоделювати збій реєстру")
    return parser


def run(args: argparse.Namespace) -> str:
    if args.command == "seed":
        create_demo_data(args.data, date.today())
        return f"Демонстраційні дані збережено: {args.data}"
    if args.command == "reserve":
        result = build_app(args.data).reservations.reserve(
            args.phone, args.pharmacy, args.drug, args.qty, args.recipe)
        return (f"Резервування {result.code} створено: {result.trade_name}, партія {result.series}, "
                f"{result.quantity} уп. Дійсне до {result.expires_at:%d.%m.%Y %H:%M}")
    result = build_app(args.data, not args.registry_down).sales.sell(args.pharmacist, args.recipe, args.qty)
    return (f"Продаж {result.number} оформлено: {result.trade_name}, партія {result.series}, "
            f"{result.quantity} уп., до сплати {result.total} грн")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        print(run(args))
    except Refused as refusal:
        print(f"Відмова (потік {refusal.flow}): {refusal}")
        return 1
    except DomainError as error:
        print(f"Відмова: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
