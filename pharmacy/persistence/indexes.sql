-- Індекси для найчастіших запитів (обґрунтування: lab7/results/query_plans.txt).
CREATE INDEX idx_drug_inn ON drug (inn);
CREATE INDEX idx_batch_pharmacy_drug ON batch (pharmacy_number, drug_id);
CREATE INDEX idx_reservation_customer_state ON reservation (customer_phone, state);
