# ІС «Мережа аптек»

Наскрізний проєкт лабораторних робіт 1–7 з дисципліни «Проєктування та розробка інформаційних
систем», варіант 3: пошук ліків у наявності, резервування, продаж за електронним рецептом.

Виконали: Гладун Олександр, Дідур Володимир, Дидо Ростислав, група КНм-26-1, Хмельницький національний університет.

## Лабораторні роботи

| № | Тема | Папка | Тег Git |
|---|---|---|---|
| 1 | Збір та аналіз вимог | [lab1](lab1) | `lab1` |
| 2 | Моделювання предметної області | [lab2](lab2) | `lab2` |
| 3 | Функціональне моделювання, варіанти використання | [lab3](lab3) | `lab3` |
| 4 | Моделювання динамічної поведінки | [lab4](lab4) | `lab4` |
| 5 | Архітектурне проєктування | [lab5](lab5) | `lab5` |
| 6 | Детальне проєктування класів і шаблони | [lab6](lab6) | `lab6` |
| 7 | Шар управління даними та тестування | [lab7](lab7) | `lab7` |

Кожна робота має окремий коміт і тег, тому стан проєкту на будь-якому етапі можна відновити командою
`git checkout lab5`. Коміт зміни вимоги R2.2 після ЛР 7 є частиною регресійного тестування.

## Структура

```text
lab1/ ... lab7/   артефакти, програми-інструменти й тести кожної роботи
pharmacy/         застосунок, створений у ЛР 5 і розвинений у ЛР 6–7
  ui/             консольний інтерфейс
  controllers/    контролери варіантів використання UC2 і UC7
  network/        шлюз до реєстру е-рецептів
  persistence/    репозиторії (пам'ять і SQLite), schema.sql, seed.sql
  domain/         доменні класи, машина станів, ціноутворення
  foundation/     винятки, контракти, час
tests/            тести застосунку
tools/            рендеринг діаграм
```

Файли `lab2/domain.py` і `lab3/prescription_sale.py` є знімками своїх етапів. Актуальний код лежить у
пакеті `pharmacy`.

## Запуск

Потрібен Python 3.10 або новіший (перевірено на 3.10, 3.12 і 3.14).

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
./run_all_tests.sh
```

Застосунок:

```bash
.venv/bin/python -m pharmacy.ui.cli seed
.venv/bin/python -m pharmacy.ui.cli reserve --phone +380671112233 --pharmacy А-01 --drug Парацетамол --qty 2
.venv/bin/python -m pharmacy.ui.cli sell --pharmacist Ф-7 --recipe E-100 --qty 1
```

Покриття коду:

```bash
.venv/bin/python -m pytest tests --cov=pharmacy --cov-branch --cov-report=term-missing
```

## Програми лабораторних

Програми запускаються з папки відповідної роботи, коли середовище активоване командою
`source .venv/bin/activate`.

**lab1**

```bash
python srs_report.py srs.yaml SRS.md
python validate.py srs.yaml
python validate.py bad_srs.yaml
```

**lab2**

```bash
python brainstorm.py domain.txt brainstorm.csv
python dmcd.py classification.csv domain.puml
python review.py classification.csv
```

**lab3**

```bash
python ucd.py use_cases.yaml -o diagrams
python trace.py ../lab1/srs.yaml use_cases.yaml --capacity 10 --tests . --functional-only
python cli.py sell --recipe E-100 --qty 1
```

**lab4**

```bash
python seq_gen.py uc7_sale.csv -o diagrams/uc7_sale.puml
python seq_gen.py uc7_broken.csv
python crude.py uc7_sale.csv uc2_reserve.csv
python fsm_check.py transitions.csv
python fsm_check.py transitions_broken.csv
```

**lab5**

```bash
python arch_check.py ../pharmacy --rules layers.yaml
```

**lab6**

```bash
python metrics.py ../pharmacy --max-methods 10 --max-fanout 5
```

**lab7**

```bash
python check_constraints.py
python query_plans.py
python schema_diagram.py
```

## Обмеження

Мережа, її дані та учасники є навчальним припущенням. Реєстр е-рецептів замінено локальною реалізацією з
тим самим інтерфейсом. Варіанти використання UC2 і UC7 реалізовано наскрізно, а решта описані в моделях.
