# Таблиця трасування «класи – таблиці»

Номери правил відповідають правилам Tegarden [1, с. 299–300].

| Елемент моделі | Таблиця, стовпець, ключ | Правило |
|---|---|---|
| клас Мережа аптек | `pharmacy_chain`, ключ `chain_id` | 1 |
| клас Аптека | `pharmacy`, ключ `number` | 1 |
| клас Фармацевт | `pharmacist`, ключ `personnel_number` | 1 |
| клас Препарат | `drug`, ключ `drug_id` | 1 |
| клас Рецептурний препарат | `prescription_drug`, ключ `drug_id` | 8a |
| клас Безрецептурний препарат | `otc_drug`, ключ `drug_id` | 8a |
| клас Партія | `batch`, ключ `batch_id`, а строк придатності в `drug_series` | 1, нормалізація |
| клас Постачальник | `supplier`, ключ `supplier_id` | 1 |
| клас Поставка | `delivery`, ключ `invoice_number` | 1 |
| клас Покупець | `customer`, ключ `phone` | 1 |
| клас Резервування | `reservation`, ключ `code` | 1 |
| клас Лікар | `doctor`, ключ `doctor_id` | 1 |
| клас Електронний рецепт | `prescription`, ключ `number` | 1 |
| клас Продаж | `sale`, ключ `number` | 1 |
| асоціативний клас Позиція продажу | `sale_line`, ключ `(sale_number, batch_id)` | 6 |
| однозначні атрибути всіх класів | стовпці відповідних таблиць | 2 |
| атрибути «закупівельна ціна», «роздрібна ціна», «сума чека», «ціна за упаковку» | стовпці `*_kop`, цілі копійки | 2 |
| атрибут «частка реімбурсації» | `prescription.reimbursement_bp`, соті частки відсотка | 2 |
| методи класів | модулі Python, збережені процедури не використано | 3 |
| Мережа складається з аптек (1 – 1..*) | `pharmacy.chain_id` → `pharmacy_chain` | 4, 7 |
| Фармацевт працює в аптеці (0..* – 1) | `pharmacist.pharmacy_number` → `pharmacy` | 4, 7 |
| Аптека зберігає партії (1 – 0..*) | `batch.pharmacy_number` → `pharmacy` | 4, 7 |
| Партія містить препарат (0..* – 1) | `batch.(drug_id, series)` → `drug_series` → `drug` | 4, 7 |
| Поставка містить партії (1 – 1..*) | `batch.invoice_number` → `delivery` | 4, 7 |
| Постачальник виконує поставку (1 – 0..*) | `delivery.supplier_id` → `supplier` | 4, 7 |
| Покупець створює резервування (1 – 0..3) | `reservation.customer_phone` → `customer` | 4, 7 |
| Резервування блокує партію (0..* – 1) | `reservation.batch_id` → `batch` | 4, 7 |
| Лікар виписує рецепт (1 – 0..*) | `prescription.doctor_id` → `doctor` | 4, 7 |
| Рецепт підтверджує резервування (0..1 – 0..1) | `reservation.prescription_number` UNIQUE → `prescription` | 4 |
| Фармацевт оформлює продаж (1 – 0..*) | `sale.personnel_number` → `pharmacist` | 4, 7 |
| Покупець здійснює покупку (0..1 – 0..*) | `sale.customer_phone` → `customer` | 4, 7 |
| Продаж погашає рецепт (0..1 – 0..1) | `sale.prescription_number` UNIQUE → `prescription` | 4 |
| Продаж охоплює партії (0..* – 1..*) | `sale_line` | 6 |

**Вибір правила для успадкування.** Для ієрархії препаратів обрано правило 8a. Рецептурні й
безрецептурні препарати мають спільні зв'язки з партіями, тому партія посилається на один ключ
`drug_id`. За правилом 8b атрибути суперкласу копіювалися б у дві таблиці, а зовнішній ключ партії
мав би посилатися на дві різні таблиці.

## Інваріанти класів у схемі

| Інваріант (ЛР 6) | Обмеження SQL |
|---|---|
| `Batch`: `quantity >= 0` | `CHECK (quantity >= 0)` |
| `Batch`: `0 <= reserved <= quantity` | `CHECK (reserved BETWEEN 0 AND quantity)` |
| `Reservation`: `1 <= quantity <= 5` | `CHECK (quantity BETWEEN 1 AND 5)` |
| `Reservation`: `extensions <= 1` | `CHECK (extensions BETWEEN 0 AND 1)` |
| `Reservation`: `expires_at > created_at` | `CHECK (expires_at > created_at)` |
| `EPrescription`: `prescribed_quantity >= 1` | `CHECK (prescribed_quantity >= 1)` |
| `EPrescription`: `0 <= share <= 1` | `CHECK (reimbursement_bp BETWEEN 0 AND 10000)` |
| `Sale`: `total >= 0` | `CHECK (total_kop >= 0)` |
| стани й способи оплати | `CHECK (... IN (...))` |
| один рецепт на один продаж і одне резервування | `UNIQUE (prescription_number)` |

Інваріант `Customer` (не більше 3 активних резервувань) потребує підрахунку рядків, тому він
виражається не обмеженням `CHECK`, а лише в доменному коді. Для нього довелося б писати тригер.
