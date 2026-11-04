# Перевірка схеми на відповідність 3НФ

Усі таблиці перебувають у 1НФ: значення атомарні, повторюваних груп немає (призначення й
позиції винесено в окремі рядки).

| Таблиця | Функціональні залежності | Висновок |
|---|---|---|
| `pharmacy_chain` | `chain_id → name, edrpou`; `edrpou → chain_id` | ключ простий, детермінанти є потенційними ключами |
| `pharmacy` | `number → chain_id, address, city, phone, schedule` | ключ простий, транзитивних залежностей немає: адреса не визначає місто однозначно |
| `pharmacist` | `personnel_number → full_name, pharmacy_number` | 3НФ |
| `drug` | `drug_id → trade_name, inn, dosage_form, dosage, manufacturer`; `trade_name → drug_id` | 3НФ |
| `prescription_drug`, `otc_drug` | `drug_id → control_group`, `drug_id → check_limit` | 3НФ |
| `drug_series` | `(drug_id, series) → expiry_date` | неключовий стовпець залежить від усього ключа |
| `batch` | `batch_id → drug_id, series, pharmacy_number, invoice_number, ціни, quantity, reserved`; `(drug_id, series, pharmacy_number) → batch_id` | 3НФ після винесення строку придатності |
| `supplier`, `delivery` | `supplier_id → name, phone`; `invoice_number → delivery_date, supplier_id` | 3НФ |
| `customer`, `doctor` | `phone → full_name`; `doctor_id → full_name, specialty` | 3НФ |
| `prescription` | `number → issued_on, inn, prescribed_quantity, reimbursement_bp, state, doctor_id` | 3НФ |
| `reservation` | `code → усі інші стовпці` | 3НФ |
| `sale` | `number → sold_at, payment_method, total_kop, personnel_number, customer_phone, prescription_number` | 3НФ із застереженням нижче |
| `sale_line` | `(sale_number, batch_id) → quantity, unit_price_kop` | неключові стовпці залежать від усього ключа, тому часткових залежностей немає |

## Знайдене порушення і нормалізація

Пряме відображення класу «Партія» дало б таблицю `batch` зі стовпцем `expiry_date`. Але одна
серія препарату може надійти в кілька аптек, а строк придатності визначає виробник для всієї
серії. Отже, існує залежність `(drug_id, series) → expiry_date`, де детермінант не є ключем таблиці.
Це транзитивна залежність, тому таблиця не перебувала б у 3НФ.

**Приклад аномалії.** Серія `PA-1` лежить в аптеках А-01 і А-02. Виробник уточнює строк
придатності. Якщо оновити лише рядок аптеки А-01, у базі буде два різні строки для однієї серії, і
прострочений препарат в аптеці А-02 можна буде продати.

**Нормалізація.** Строк придатності винесено в таблицю `drug_series` із ключем `(drug_id, series)`.
Таблиця `batch` посилається на неї складеним зовнішнім ключем. Доменний клас `Batch` не змінився:
репозиторій збирає його з двох таблиць. Результат перевіряє тест
`test_sqlite_series_keeps_single_expiry_date_for_two_pharmacies`.

## Свідома денормалізація

`sale.total_kop` можна було б обчислити за позиціями та часткою реімбурсації. Стовпець залишено,
бо сума чека є історичним фактом: вона не повинна змінюватися, якщо пізніше зміниться алгоритм
ціноутворення. З тієї самої причини `sale_line.unit_price_kop` зберігає ціну на момент продажу, а
не посилання на поточну роздрібну ціну партії.

Стовпець «доступний залишок» не зберігається: значення `quantity - reserved` обчислюється, інакше
було б транзитивну залежність.
