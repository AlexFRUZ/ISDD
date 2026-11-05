CREATE INDEX idx_drug_inn ON drug (inn);
CREATE INDEX idx_batch_pharmacy_drug ON batch (pharmacy_number, drug_id);
CREATE INDEX idx_reservation_customer_state ON reservation (customer_phone, state);
CREATE INDEX idx_reservation_state_expires ON reservation (state, expires_at);
CREATE INDEX idx_drug_series_expiry ON drug_series (expiry_date);
CREATE INDEX idx_sale_sold_at ON sale (sold_at);
CREATE INDEX idx_write_off_batch ON write_off (batch_id);
