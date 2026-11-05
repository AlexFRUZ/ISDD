# Етапи 3–4. Моделі та проєктні рішення підсистеми «Склад і звітність»

## Власні й спільні класи

| Клас | Належність | Таблиця |
|---|---|---|
| `Delivery`, `Supplier` | власні | `delivery`, `supplier` |
| `WriteOff`, `WriteOffReason` | власні | `write_off` |
| `Manager`, `Director` | власні (ролі) | `manager`, `director` |
| `SalesReport`, `PharmacySalesRow` | власні, обчислювані | — |
| `Batch`, `Drug`, `Pharmacy` | спільне ядро | `batch`, `drug_series`, `drug`, `pharmacy` |
| `Sale` | підсистема «Продаж», лише читання | `sale`, `sale_line` |

## Пакети

| Рівень | Реалізація |
|---|---|
| UI | `receive`, `write-off`, `expiring`, `sales-report` у `pharmacy/ui/cli.py` |
| Controllers | `pharmacy/controllers/warehouse` |
| Persistence | `ManagerRepository`, `DirectorRepository`, `SupplierRepository`, `DeliveryRepository`, `WriteOffRepository` |
| Domain | `supply.py`, `report.py`, `chain.py` (`Manager`, `Director`), `batch.py` |

## GRASP і GoF

| Рішення | Шаблон | Обґрунтування |
|---|---|---|
| окремий контролер на UC10–UC13 | Controller | один контролер на запит актора |
| `Pharmacy.expiring_batches` | Information Expert | аптека володіє колекцією партій |
| `Batch.write_off`, `days_until_expiry` | Information Expert | партія знає залишок, резерв і строк |
| `Manager.may_view`, `Director.may_view` | Polymorphism | політика видимості без умов у контролері |
| `SalesReport.build` | Information Expert / Pure Fabrication | звіт агрегує рядки й підсумки |
| `DeliveryValidator` | Pure Fabrication | знижує зв'язність контролера приймання |
| `WriteOff` створює контролер | Creator | контролер має всі дані акта |

## Контракти

### `ReceiveDeliveryController.receive`

- передумови: непорожня накладна й номер; кількість ≥ 1; ціни ≥ 0;
- перевірки: завідувач, унікальність накладної, постачальник, каталог, строк, серія;
- постумови: створено `Delivery` і по партії на позицію, партії є в `Pharmacy.batches`;
- атомарність: відмова будь-якої позиції не залишає жодної партії чи поставки.

### `WriteOffController.write_off`

- передумови: кількість ≥ 1, якщо задана;
- перевірки: партія аптеки завідувача, причина зі списку, кількість ≤ `available`;
- постумови: `quantity` зменшилась точно на списану кількість, `reserved` не змінився, створено акт.

### `ExpiryController.expiring`

- передумова: горизонт ≥ 0; постумова: стан не змінюється;
- результат: партії аптеки із залишком, строк яких настає не пізніше ніж через `days`.

### `SalesReportController.report`

- перевірки: користувач — завідувач або директор, період коректний, аптека доступна ролі;
- результат: рядок на кожну аптеку обсягу (включно з нульовими) і підсумки.

## Дані та 3НФ

`delivery` зберігає заголовок накладної й посилання на `supplier`; партія посилається на накладну
через `batch.invoice_number`, тому дані постачальника не дублюються. `write_off` посилається на
партію й завідувача й не дублює назву препарату чи аптеку. Сума звіту не зберігається, а обчислюється
із чеків, тому розбіжностей не виникає. Індекси `idx_sale_sold_at` і `idx_drug_series_expiry`
прискорюють вибірки UC13 і UC12 у СУБД.

## Інтеграція

Підсистема не імпортує контролерів інших підсистем. Із «Продажу» використовується тільки сховище
чеків, із «Резервування» — стан `Batch.reserved`, який списання не змінює. Правило перевіряє
`arch_check.py`.
