from __future__ import annotations

import argparse
import sys
from contextlib import closing

from pharmacy.controllers.factory import build_app, create_demo_data
from pharmacy.foundation.errors import DomainError, Refused

DEFAULT_DATA = "pharmacy.sqlite3"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pharmacy", description="ІС «Мережа аптек»")
    parser.add_argument("--data", default=DEFAULT_DATA, help="файл бази даних SQLite")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("seed", help="створити демонстраційні дані")

    reserve = commands.add_parser("reserve", help="UC2 Зарезервувати препарат")
    reserve.add_argument("--phone", required=True)
    reserve.add_argument("--pharmacy", required=True)
    reserve.add_argument("--drug", required=True)
    reserve.add_argument("--qty", type=int, default=1)
    reserve.add_argument("--recipe")

    cancel = commands.add_parser("cancel", help="UC3 Скасувати резервування")
    cancel.add_argument("--phone", required=True)
    cancel.add_argument("--code", required=True)

    prepare = commands.add_parser("prepare", help="UC4 Підготувати резерв")
    prepare.add_argument("--pharmacist", required=True)
    prepare.add_argument("--code", required=True)
    prepare.add_argument("--sms-down", action="store_true", help="змоделювати збій SMS-шлюзу")

    extend = commands.add_parser("extend", help="UC5 Продовжити резервування")
    extend.add_argument("--pharmacist", required=True)
    extend.add_argument("--code", required=True)

    commands.add_parser("expire", help="анулювати прострочені резервування")

    sell = commands.add_parser("sell", help="UC7 Продати за е-рецептом")
    sell.add_argument("--pharmacist", required=True)
    sell.add_argument("--recipe", required=True)
    sell.add_argument("--qty", type=int, default=1)
    sell.add_argument("--registry-down", action="store_true", help="змоделювати збій реєстру")
    return parser


def run(args: argparse.Namespace) -> str:
    if args.command == "seed":
        create_demo_data(args.data)
        return f"Демонстраційні дані збережено: {args.data}"
    if args.command == "reserve":
        with closing(build_app(args.data)) as app:
            result = app.reservations.reserve(args.phone, args.pharmacy, args.drug, args.qty, args.recipe)
        return (f"Резервування {result.code} створено: {result.trade_name}, партія {result.series}, "
                f"{result.quantity} уп. Дійсне до {result.expires_at:%d.%m.%Y %H:%M}")
    if args.command == "cancel":
        with closing(build_app(args.data)) as app:
            status = app.cancellation.cancel(args.phone, args.code)
        return f"Резервування {status.code} скасовано"
    if args.command == "prepare":
        with closing(build_app(args.data, sms_online=not args.sms_down)) as app:
            status = app.preparation.prepare(args.pharmacist, args.code)
        notice = "покупця сповіщено" if status.notified else "сповіщення не надіслано"
        return f"Резервування {status.code} готове, {notice}"
    if args.command == "extend":
        with closing(build_app(args.data)) as app:
            status = app.extension.extend(args.pharmacist, args.code)
        return f"Резервування {status.code} продовжено до {status.expires_at:%d.%m.%Y %H:%M}"
    if args.command == "expire":
        with closing(build_app(args.data)) as app:
            codes = app.expiration.expire_overdue()
        return f"Анульовано резервувань: {len(codes)}"
    with closing(build_app(args.data, not args.registry_down)) as app:
        result = app.sales.sell(args.pharmacist, args.recipe, args.qty)
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
