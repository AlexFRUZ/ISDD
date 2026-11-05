# Матриця трасування підсистеми «Продаж»

| Вимога | UC6 | UC7 | UC8 | UC9 | Автоматична перевірка |
|---|---:|---:|---:|---:|---|
| R5, R5.1–R5.3 | X |  |  |  | `tests/test_sales_subsystem.py::test_uc6_*` |
| R6, R6.1–R6.5 |  | X |  | X | `tests/test_controllers.py`, `tests/test_uc7_integration.py` |
| R7, R7.1–R7.2 |  |  | X |  | `tests/test_sales_subsystem.py::test_uc8_*` |
| R8, R8.1 | X | X | X |  | UC6/UC7/UC8 tests, FEFO boundary |
| N2 | X | X | X |  | демонстраційний запуск; час зовнішнього реєстру виключено |
| N5 | X | X | X |  | невідомий табельний номер відхиляється |
| R2.4 |  |  |  | X | інтеграційний тест UC2 → UC9 |

Порожніх рядків і стовпців немає. Повна матриця проєкту зберігається в `lab3/RUTM.md`.
