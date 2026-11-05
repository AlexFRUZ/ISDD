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
