from datetime import date, timedelta

import pytest

from pharmacy.ui import cli


@pytest.fixture
def run(tmp_path, capsys):
    database = str(tmp_path / "test.sqlite3")

    def invoke(*args):
        code = cli.main(["--data", database, *args])
        return code, capsys.readouterr().out

    assert invoke("seed")[0] == 0
    return invoke


def test_seed_creates_database(run):
    assert run("seed")[1].startswith("Демонстраційні дані збережено")


def test_reserve_prints_code(run):
    code, out = run("reserve", "--phone", "+380671112233", "--pharmacy", "А-01", "--drug", "Парацетамол", "--qty", "2")
    assert code == 0 and "Резервування R-6 створено" in out and "партія PA-1" in out


def test_state_survives_between_runs(run):
    assert run("sell", "--pharmacist", "Ф-7", "--recipe", "E-100", "--qty", "2")[0] == 0
    code, out = run("sell", "--pharmacist", "Ф-7", "--recipe", "E-100")
    assert code == 1 and "погашений" in out


def test_sale_prints_amount(run):
    code, out = run("sell", "--pharmacist", "Ф-7", "--recipe", "E-101", "--qty", "2")
    assert code == 0 and "до сплати 180.00 грн" in out


def test_refusal_prints_flow(run):
    code, out = run("sell", "--pharmacist", "Ф-7", "--recipe", "E-999")
    assert code == 1 and "потік 3a" in out


def test_registry_down_flag(run):
    code, out = run("sell", "--pharmacist", "Ф-7", "--recipe", "E-100", "--registry-down")
    assert code == 1 and "потік 6a" in out


def test_contract_violation_is_reported_without_traceback(run):
    code, out = run("sell", "--pharmacist", "Ф-7", "--recipe", "E-100", "--qty", "0")
    assert code == 1 and out.startswith("Відмова: Кількість має бути додатною")


def test_cancel_command(run):
    run("reserve", "--phone", "+380671112233", "--pharmacy", "А-01", "--drug", "Парацетамол")
    code, out = run("cancel", "--phone", "+380671112233", "--code", "R-6")
    assert code == 0 and "R-6 скасовано" in out


def test_prepare_and_extend_commands(run):
    run("reserve", "--phone", "+380671112233", "--pharmacy", "А-01", "--drug", "Парацетамол")
    assert "покупця сповіщено" in run("prepare", "--pharmacist", "Ф-7", "--code", "R-6")[1]
    assert "продовжено до" in run("extend", "--pharmacist", "Ф-7", "--code", "R-6")[1]


def test_prepare_with_sms_down(run):
    run("reserve", "--phone", "+380671112233", "--pharmacy", "А-01", "--drug", "Парацетамол")
    assert "сповіщення не надіслано" in run("prepare", "--pharmacist", "Ф-7", "--code", "R-6", "--sms-down")[1]


def test_expire_command(run):
    code, out = run("expire")
    assert code == 0 and out.startswith("Анульовано резервувань: 0")


def test_issue_reserved_sale_command(run):
    run("reserve", "--phone", "+380671112233", "--pharmacy", "А-01", "--drug", "Парацетамол")
    run("prepare", "--pharmacist", "Ф-7", "--code", "R-6")
    code, out = run("issue", "--pharmacist", "Ф-7", "--code", "R-6")
    assert code == 0 and "Продаж Ч-6 оформлено" in out and "35.50 грн" in out


def test_otc_sale_command(run):
    code, out = run("sell-otc", "--pharmacist", "Ф-7", "--drug", "Парацетамол", "--qty", "2")
    assert code == 0 and "PA-0" in out and "60.00 грн" in out


def test_verify_recipe_command(run):
    code, out = run("verify-recipe", "--recipe", "E-100")
    assert code == 0 and "Рецепт E-100 чинний" in out


def test_verify_recipe_registry_down(run):
    code, out = run("verify-recipe", "--recipe", "E-100", "--registry-down")
    assert code == 1 and "потік 2a" in out


def test_receive_then_expiring_and_write_off(run):
    soon = (date.today() + timedelta(days=10)).isoformat()
    code, out = run("receive", "--manager", "З-1", "--invoice", "Н-10", "--supplier", "Оптима-Фарм",
                    "--line", f"Парацетамол;PA-2;{soon};20;35.50;30")
    assert code == 0 and "Поставку Н-10" in out and "разом 30 уп" in out
    code, out = run("expiring", "--manager", "З-1")
    assert code == 0 and "PA-2" in out and "PA-0" in out
    code, out = run("write-off", "--manager", "З-1", "--drug", "Парацетамол", "--series", "PA-2",
                    "--reason", "пошкодження", "--qty", "10")
    assert code == 0 and "Акт С-1" in out and "Залишок 20 уп" in out
    assert run("receive", "--manager", "З-1", "--invoice", "Н-10", "--supplier", "Оптима-Фарм",
               "--line", "Парацетамол;PA-3;2030-01-01;1;2;3")[1].startswith("Відмова (потік 3a)")


def test_receive_rejects_malformed_line(run):
    code, out = run("receive", "--manager", "З-1", "--invoice", "Н-11", "--supplier", "Оптима-Фарм", "--line", "x;y")
    assert code == 1 and "шість полів" in out
    code, out = run("receive", "--manager", "З-1", "--invoice", "Н-11", "--supplier", "Оптима-Фарм",
                    "--line", "Парацетамол;PA-2;вчора;20;35;3")
    assert code == 1 and "некоректну" in out


def test_expiring_prints_empty_message(run):
    code, out = run("expiring", "--manager", "З-3", "--days", "0")
    assert code == 0 and "немає" in out


def test_sales_report_for_director_and_manager(run):
    run("sell-otc", "--pharmacist", "Ф-7", "--drug", "Парацетамол", "--qty", "2")
    today = date.today().isoformat()
    code, out = run("sales-report", "--user", "Д-1", "--from", today, "--to", today)
    assert code == 0 and "А-01" in out and "Разом: чеків 1, упаковок 2" in out
    code, out = run("sales-report", "--user", "З-2", "--from", today, "--to", today)
    assert code == 0 and "А-01" not in out and "Разом: чеків 0" in out


def test_sales_report_refusals(run):
    assert "потік 4b" in run("sales-report", "--user", "З-1", "--from", "2026-01-01", "--to", "2026-01-02",
                             "--pharmacy", "А-02")[1]
    code, out = run("sales-report", "--user", "Д-1", "--from", "2026/01/01", "--to", "2026-01-02")
    assert code == 1 and "РРРР-ММ-ДД" in out
