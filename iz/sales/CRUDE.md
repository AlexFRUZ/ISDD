# Матриця CRUDE підсистеми «Продаж»

| Клієнт \ сервер | ReservationProvider | PrescriptionVerificationService | Sale | SaleLine | EPrescription | Reservation | Batch | DBMgr |
|---|---|---|---|---|---|---|---|---|
| ReservedSaleController | R U | R U | C | C | R U | R U | U | R U |
| PrescriptionSaleController |  | R U | C | C | R U |  | U | R U |
| OtcSaleController |  |  | C | C |  |  | R U | R U |
| PrescriptionVerificationService |  |  |  |  | R U |  |  | R U |
| Sale |  |  |  | C R | R | R | U |  |
| Reservation |  |  |  |  | R |  | U |  |

Позначення: C — створює, R — читає, U — змінює, D — видаляє, E — виконує. Найбільший fan-out
очікувано мають контролери UC6 і UC7; зовнішні системи ізольовані сервісом та інтерфейсом.
