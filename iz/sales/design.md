# Етапи 3–4. Моделі та проєктні рішення підсистеми «Продаж»

## Власні й спільні класи

| Клас | Належність | Таблиця |
|---|---|---|
| `Sale`, `SaleLine` | власні | `sale`, `sale_line` |
| `EPrescription`, `Doctor` | власні для UC9 | `prescription`, `doctor` |
| `Reservation` | підсистема «Резервування», доступ через інтерфейс | `reservation` |
| `Batch`, `Drug`, `Pharmacist` | спільне ядро | `batch`, `drug`, `pharmacist` |

## Пакети

| Рівень | Реалізація |
|---|---|
| UI | `issue`, `sell`, `sell-otc`, `verify-recipe` у `pharmacy/ui/cli.py` |
| Controllers | `pharmacy/controllers/sales` |
| Network | `PrescriptionRegistry`, `LocalRegistry` |
| Persistence | `SaleRepository`, `PrescriptionRepository`, `UnitOfWork` |
| Domain | `sale.py`, `prescription.py`, спільні `batch.py`, `chain.py` |

## GRASP і GoF

| Рішення | Шаблон | Обґрунтування |
|---|---|---|
| окремий контролер UC6, UC7, UC8 | Controller | один контролер на запит актора |
| перевірка стану рецепта в `EPrescription` | Information Expert | рецепт володіє станом і датою виписки |
| добір FEFO в `Pharmacy` | Information Expert | аптека володіє колекцією партій |
| створення `SaleLine` класом `Sale` | Creator | чек агрегує позиції |
| `PrescriptionVerificationService` | Pure Fabrication / Facade | одна точка доступу до реєстру для трьох use cases |
| `PrescriptionRegistry` | Adapter/Bridge | контролери не залежать від API зовнішнього реєстру |
| `PricingPolicy` | Strategy | стандартна ціна та реімбурсація без умов у контролері |

## Контракти

### `ReservedSaleController.issue`

- передумови: додаток має `UnitOfWork`; передано табельний номер і код;
- перевірки: фармацевт існує, резерв у його аптеці, стан готовий/продовжений, строк не минув;
- постумови: створено один чек, резерв має стан «Видане», `reserved` зменшено, `quantity` списано;
- атомарність: помилка запису чека відкочує стан резерву, рецепт і залишок.

### `PrescriptionSaleController.sell`

- передумови: `quantity >= 1`;
- постумови: рецепт погашено, партію списано, сума враховує `PricingPolicy`;
- відмова: не змінює рецепт, залишок і послідовність номерів.

### `OtcSaleController.sell`

- передумови: `quantity >= 1`;
- перевірки: препарат є `OtcDrug`, кількість не перевищує `check_limit`;
- постумови: вибрано найранішу непрострочену партію, створено чек і списано кількість.

### `PrescriptionVerificationService.verify`

- результат: активний рецепт у межах 30 днів;
- винятки: контрольовані потоки `2a`, `3a`, `3b`, а для інтеграції з UC2 — `6b`.

## Машина станів

Для `EPrescription` визначено стани «активний», «погашений», «скасований». Продаж дозволений лише з
активного стану; успішне погашення є незворотним. Діаграма — `diagrams/prescription_states.puml`.

## Дані та 3НФ

`sale` зберігає заголовок чека, а `sale_line` — позиції. Часткова залежність ціни й кількості від чека
усунута винесенням позицій. `prescription` окремо посилається на `doctor`; дані лікаря не дублюються.
Унікальний `sale.prescription_number` гарантує один продаж за рецептом, а `sale_line` має складений
первинний ключ `(sale_number, batch_id)`. Сума зберігається свідомо як денормалізований фінансовий
знімок чека; її узгодженість забезпечують доменний контракт і тести.

## Інтеграція

UC6 викликає тільки `ReservationProvider`. UC2 використовує тільки `verified_for`. Правило перевіряє
`arch_check.py`; прямі імпорти внутрішніх модулів іншої підсистеми заборонено.
