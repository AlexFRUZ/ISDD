from __future__ import annotations

import argparse
import sys
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation

from pharmacy.controllers.factory import build_app, create_demo_data
from pharmacy.controllers.warehouse import DeliveryLine
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

    issue = commands.add_parser("issue", help="UC6 Видати резерв")
    issue.add_argument("--pharmacist", required=True)
    issue.add_argument("--code", required=True)
    issue.add_argument("--payment", choices=["готівка", "картка"], default="картка")

    otc = commands.add_parser("sell-otc", help="UC8 Продати безрецептурний препарат")
    otc.add_argument("--pharmacist", required=True)
    otc.add_argument("--drug", required=True)
    otc.add_argument("--qty", type=int, default=1)
    otc.add_argument("--payment", choices=["готівка", "картка"], default="картка")

    verify = commands.add_parser("verify-recipe", help="UC9 Перевірити е-рецепт")
    verify.add_argument("--recipe", required=True)
    verify.add_argument("--registry-down", action="store_true", help="змоделювати збій реєстру")

    receive = commands.add_parser("receive", help="UC10 Прийняти поставку")
    receive.add_argument("--manager", required=True)
    receive.add_argument("--invoice", required=True)
    receive.add_argument("--supplier", required=True)
    receive.add_argument("--line", action="append", required=True, metavar="НАЗВА;СЕРІЯ;ДО;ЗАКУПКА;РОЗДРІБ;КІЛЬКІСТЬ",
                         help="позиція накладної, наприклад Парацетамол;PA-2;2027-12-31;20;35.50;30")

    write_off = commands.add_parser("write-off", help="UC11 Списати партію")
    write_off.add_argument("--manager", required=True)
    write_off.add_argument("--drug", required=True)
    write_off.add_argument("--series", required=True)
    write_off.add_argument("--reason", required=True)
    write_off.add_argument("--qty", type=int, help="за замовчуванням списується весь вільний залишок")

    expiring = commands.add_parser("expiring", help="UC12 Переглянути строки придатності")
    expiring.add_argument("--manager", required=True)
    expiring.add_argument("--days", type=int, default=30)

    report = commands.add_parser("sales-report", help="UC13 Сформувати звіт про продажі")
    report.add_argument("--user", required=True, help="табельний номер завідувача або директора")
    report.add_argument("--from", dest="start", required=True, help="початок періоду РРРР-ММ-ДД")
    report.add_argument("--to", dest="end", required=True, help="кінець періоду РРРР-ММ-ДД")
    report.add_argument("--pharmacy")
    return parser


def parse_line(text: str) -> DeliveryLine:
    parts = text.split(";")
    if len(parts) != 6:
        raise DomainError(f"Позиція «{text}» має містити шість полів, розділених «;»")
    try:
        return DeliveryLine(parts[0], parts[1], date.fromisoformat(parts[2]), Decimal(parts[3]),
                            Decimal(parts[4]), int(parts[5]))
    except (ValueError, InvalidOperation):
        raise DomainError(f"Позиція «{text}» містить некоректну дату, ціну або кількість") from None


def parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise DomainError(f"Дата «{text}» має бути у форматі РРРР-ММ-ДД") from None


def warehouse_run(args: argparse.Namespace) -> str:
    with closing(build_app(args.data)) as app:
        if args.command == "receive":
            result = app.deliveries.receive(args.manager, args.invoice, args.supplier,
                                            [parse_line(line) for line in args.line])
            items = "; ".join(f"{name} {series} — {qty} уп." for name, series, qty in result.batches)
            return (f"Поставку {result.invoice_number} від {result.supplier} прийнято в аптеку "
                    f"{result.pharmacy_number}: {items}; разом {result.packs} уп")
        if args.command == "write-off":
            done = app.write_offs.write_off(args.manager, args.drug, args.series, args.reason, args.qty)
            return (f"Акт {done.number}: списано {done.written_off} уп. {done.trade_name}, партія {done.series} "
                    f"({done.reason}). Залишок {done.remaining} уп.")
        if args.command == "expiring":
            rows = app.expiry.expiring(args.manager, args.days)
            if not rows:
                return f"Партій, строк яких завершується протягом {args.days} днів, немає"
            lines = [f"Партії зі строком до {args.days} днів:"]
            for row in rows:
                mark = "ПРОСТРОЧЕНО" if row.expired else f"{row.days_left} дн."
                lines.append(f"  {row.trade_name} {row.series}: до {row.expiry_date:%d.%m.%Y} ({mark}), "
                             f"{row.quantity} уп., з них у резерві {row.reserved}")
            return "\n".join(lines)
        report = app.sales_reports.report(args.user, parse_date(args.start), parse_date(args.end), args.pharmacy)
    lines = [f"Звіт про продажі {report.start:%d.%m.%Y} — {report.end:%d.%m.%Y}",
             "  аптека  місто                    чеків  упаковок  виручка, грн  середній чек"]
    for row in report.rows:
        lines.append(f"  {row.pharmacy_number:<7} {row.city:<24} {row.sales_count:>5} {row.packs:>9} "
                     f"{row.revenue:>13} {row.average_check:>13}")
    lines.append(f"  Разом: чеків {report.sales_count}, упаковок {report.packs}, виручка {report.revenue} грн")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> str:
    if args.command == "seed":
        create_demo_data(args.data)
        return f"Демонстраційні дані збережено: {args.data}"
    if args.command in ("receive", "write-off", "expiring", "sales-report"):
        return warehouse_run(args)
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
    if args.command == "issue":
        with closing(build_app(args.data)) as app:
            result = app.reserved_sales.issue(args.pharmacist, args.code, args.payment)
    elif args.command == "sell-otc":
        with closing(build_app(args.data)) as app:
            result = app.otc_sales.sell(args.pharmacist, args.drug, args.qty, args.payment)
    elif args.command == "verify-recipe":
        with closing(build_app(args.data, not args.registry_down)) as app:
            recipe = app.recipe_verification.verify(args.recipe, date.today())
        return f"Рецепт {recipe.number} чинний: {recipe.inn}, {recipe.prescribed_quantity} уп."
    else:
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
