# Етапи 3 і 4. Моделі та проєктні рішення підсистеми «Резервування»

## Класи підсистеми

| Клас | Належність | Таблиця |
|---|---|---|
| `Reservation` | власний | `reservation` |
| `Customer` | власний | `customer` |
| `Batch` | спільний, змінює залишок | `batch` |
| `EPrescription` | підсистема «Продаж», лише читання | `prescription` |
| `Pharmacist`, `Pharmacy` | спільні | `pharmacist`, `pharmacy` |

## Машина станів

Найскладніший життєвий цикл має клас `Reservation`. Таблиця переходів лежить у файлі
`lab4/transitions.csv`, а результат перевірки на аномалії у `results/fsm.txt`.

## Пакети

| Рівень | Пакет підсистеми |
|---|---|
| `ui` | команди `reserve`, `cancel`, `prepare`, `extend`, `expire` у `pharmacy/ui/cli.py` |
| `controllers` | `pharmacy/controllers/reservation` |
| `network` | `pharmacy/network/sms.py` |
| `persistence` | `ReservationRepository`, `CustomerRepository` |
| `domain` | `pharmacy/domain/reservation.py`, `pharmacy/domain/customer.py` |

Файл `lab5/layers.yaml` доповнено розділом `subsystems`. `arch_check.py` забороняє підсистемам
імпортувати внутрішні модулі одна одної поза погодженим інтерфейсом.

## Розподіл відповідальностей

| Відповідальність | Шаблон | Клас | Обґрунтування |
|---|---|---|---|
| обробити запит скасування, збирання чи продовження | Controller | контролер кожного use case | один контролер на варіант використання |
| перевірити належність покупцю | Expert | `Reservation.belongs_to` | резервування знає покупця |
| перевірити аптеку резервування | Expert | `Reservation.is_at_pharmacy` | резервування знає партію й аптеку |
| перевірити прострочення | Expert | `Reservation.is_overdue` | резервування знає строк дії |
| перевірити ліміт | Expert | `Customer.can_reserve` | покупець знає свої резервування |
| створити резервування | Creator | `Customer.create_reservation` | покупець містить резервування |
| надіслати сповіщення | Pure Fabrication | `SmsGateway` | штучний клас ізолює зовнішню систему |

## Контракти операцій інтерфейсу

| Поле | `ReservationProvider.find` | `ReservationProvider.complete_issue` |
|---|---|---|
| **Клієнт** | підсистема «Продаж», UC6 | підсистема «Продаж», UC6 |
| **Аргументи** | `code: str` | `reservation: Reservation`, `moment: datetime` |
| **Результат** | `Reservation` або `None` | немає |
| **Передумови** | немає | стан «Готове» або «Продовжене», строк дії не минув |
| **Постумови** | стан не змінено | стан «Видане», залишок партії зменшено, блокування знято |
| **Винятки** | немає | `TransitionError` |

Інваріанти класів `Reservation` і `Customer` наведено в `lab6/contracts.md`.

## Шаблон GoF

Для зміни поведінки за станом застосовано таблицю переходів, яка замінює шаблон State: стани
відрізняються лише допустимими подіями. Шлюз `SmsGateway` є адаптером до зовнішньої системи: контролер
працює зі спільним інтерфейсом, а `LocalSmsGateway` можна замінити клієнтом реального провайдера.

## Таблиці бази даних

| Таблиця | Обмеження | Індекси |
|---|---|---|
| `reservation` | `CHECK` кількості 1..6, продовжень 0..1, станів, `expires_at > created_at`; `UNIQUE` рецепта | `idx_reservation_customer_state`, `idx_reservation_state_expires` |
| `customer` | первинний ключ `phone` | первинний ключ |

Обидві таблиці перебувають у 3НФ, аналіз наведено в `lab7/normalization.md`. Зовнішні ключі таблиці
`reservation` посилаються на `batch` і `customer`, а також на `prescription` підсистеми «Продаж».
Індекс `idx_reservation_state_expires` прискорює пошук прострочених резервувань.
