"""Консольний інтерфейс прототипу UC7.

Приклади:
  python cli.py sell --recipe E-100 --qty 1
  python cli.py sell --recipe E-999 --qty 1
  python cli.py sell --recipe E-100 --qty 1 --registry-down
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from demo_data import build_world
from prescription_sale import SaleRefused


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Прототип UC7 «Продати за е-рецептом»")
    commands = parser.add_subparsers(dest="command", required=True)
    sell = commands.add_parser("sell", help="оформити продаж за рецептом")
    sell.add_argument("--recipe", required=True, help="номер рецепта")
    sell.add_argument("--qty", type=int, default=1, help="кількість упаковок")
    sell.add_argument("--registry-down", action="store_true", help="змоделювати збій реєстру")
    args = parser.parse_args(argv)

    now = datetime.now()
    world = build_world(now.date())
    world.registry.online = not args.registry_down
    try:
        sale = world.service.sell(args.recipe, args.qty, now)
    except SaleRefused as refusal:
        print(f"Відмова (потік {refusal.flow}): {refusal}")
        return 1
    line = sale.lines[0]
    print(f"Продаж {sale.number} оформлено: {line.batch.drug.trade_name}, партія {line.batch.series}, "
          f"{line.quantity} уп., до сплати {sale.total} грн")
    return 0


if __name__ == "__main__":
    sys.exit(main())
