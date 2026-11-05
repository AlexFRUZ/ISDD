# Матриця CRUDE підсистеми «Склад і звітність»

| Клієнт \ сервер | Delivery | Supplier | Batch | WriteOff | Pharmacy | Manager | Director | Sale | SalesReport | DBMgr |
|---|---|---|---|---|---|---|---|---|---|---|
| ReceiveDeliveryController | C | R | C | | R | R | | | | R U |
| DeliveryValidator | | | R | | R | | | | | R |
| WriteOffController | | | R U | C | R | R | | | | R U |
| ExpiryController | | | R | | R | R | | | | R |
| SalesReportController | | | | | R | R | R | R | C | R |
| Pharmacy | | | R | | | | | | | |
| SalesReport | | | | | R | | | R | | |

Позначення: C — створює, R — читає, U — змінює, D — видаляє, E — виконує. Видалення в підсистемі
немає: списання змінює кількість партії й додає акт, тому рядок без `D` є свідомим рішенням для
обліку. Найбільший fan-out має `ReceiveDeliveryController`; перевірки позицій винесено в
`DeliveryValidator`. Звіт лише читає чеки підсистеми «Продаж» через `SaleRepository`, а не через її
контролери.

Автоматично згенерована чорнова матриця (`results/crude.txt`) помилково визначила дієслово
«списує» як `D`; у цій версії виправлено на `U`.
