CREATE TABLE pharmacy_chain (
    chain_id INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    edrpou   TEXT NOT NULL UNIQUE CHECK (length(edrpou) = 8)
);

CREATE TABLE pharmacy (
    number   TEXT PRIMARY KEY,
    chain_id INTEGER NOT NULL REFERENCES pharmacy_chain (chain_id),
    address  TEXT NOT NULL,
    city     TEXT NOT NULL,
    phone    TEXT NOT NULL,
    schedule TEXT NOT NULL
);

CREATE TABLE pharmacist (
    personnel_number TEXT PRIMARY KEY,
    full_name        TEXT NOT NULL,
    pharmacy_number  TEXT NOT NULL REFERENCES pharmacy (number)
);

CREATE TABLE manager (
    personnel_number TEXT PRIMARY KEY,
    full_name        TEXT NOT NULL,
    pharmacy_number  TEXT NOT NULL REFERENCES pharmacy (number)
);

CREATE TABLE director (
    personnel_number TEXT PRIMARY KEY,
    full_name        TEXT NOT NULL
);

CREATE TABLE drug (
    drug_id      INTEGER PRIMARY KEY,
    trade_name   TEXT NOT NULL UNIQUE,
    inn          TEXT NOT NULL,
    dosage_form  TEXT NOT NULL,
    dosage       TEXT NOT NULL,
    manufacturer TEXT NOT NULL
);

CREATE TABLE prescription_drug (
    drug_id       INTEGER PRIMARY KEY REFERENCES drug (drug_id) ON DELETE CASCADE,
    control_group TEXT NOT NULL
);

CREATE TABLE otc_drug (
    drug_id     INTEGER PRIMARY KEY REFERENCES drug (drug_id) ON DELETE CASCADE,
    check_limit INTEGER NOT NULL CHECK (check_limit >= 1)
);

CREATE TABLE drug_series (
    drug_id     INTEGER NOT NULL REFERENCES drug (drug_id),
    series      TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    PRIMARY KEY (drug_id, series)
);

CREATE TABLE supplier (
    supplier_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    phone       TEXT NOT NULL
);

CREATE TABLE delivery (
    invoice_number TEXT PRIMARY KEY,
    delivery_date  TEXT NOT NULL,
    supplier_id    INTEGER NOT NULL REFERENCES supplier (supplier_id)
);

CREATE TABLE batch (
    batch_id           INTEGER PRIMARY KEY,
    drug_id            INTEGER NOT NULL,
    series             TEXT NOT NULL,
    pharmacy_number    TEXT NOT NULL REFERENCES pharmacy (number),
    invoice_number     TEXT REFERENCES delivery (invoice_number),
    purchase_price_kop INTEGER NOT NULL CHECK (purchase_price_kop >= 0),
    retail_price_kop   INTEGER NOT NULL CHECK (retail_price_kop >= 0),
    quantity           INTEGER NOT NULL CHECK (quantity >= 0),
    reserved           INTEGER NOT NULL DEFAULT 0 CHECK (reserved BETWEEN 0 AND quantity),
    FOREIGN KEY (drug_id, series) REFERENCES drug_series (drug_id, series),
    UNIQUE (drug_id, series, pharmacy_number)
);

CREATE TABLE write_off (
    number           TEXT PRIMARY KEY,
    written_at       TEXT NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity >= 1),
    reason           TEXT NOT NULL CHECK (reason IN ('строк придатності минув', 'пошкодження',
                                                     'брак виробника', 'інша причина')),
    batch_id         INTEGER NOT NULL REFERENCES batch (batch_id),
    personnel_number TEXT NOT NULL REFERENCES manager (personnel_number)
);

CREATE TABLE customer (
    phone     TEXT PRIMARY KEY,
    full_name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE doctor (
    doctor_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    UNIQUE (full_name, specialty)
);

CREATE TABLE prescription (
    number              TEXT PRIMARY KEY,
    issued_on           TEXT NOT NULL,
    inn                 TEXT NOT NULL,
    prescribed_quantity INTEGER NOT NULL CHECK (prescribed_quantity >= 1),
    reimbursement_bp    INTEGER NOT NULL DEFAULT 0 CHECK (reimbursement_bp BETWEEN 0 AND 10000),
    state               TEXT NOT NULL CHECK (state IN ('активний', 'погашений', 'скасований')),
    doctor_id           INTEGER NOT NULL REFERENCES doctor (doctor_id)
);

CREATE TABLE reservation (
    code                TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    expires_at          TEXT NOT NULL,
    quantity            INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 6),
    extensions          INTEGER NOT NULL DEFAULT 0 CHECK (extensions BETWEEN 0 AND 1),
    state               TEXT NOT NULL CHECK (state IN ('Нове', 'Підтверджене', 'Готове', 'Продовжене',
                                                       'Видане', 'Скасоване', 'Прострочене', '[*]')),
    customer_notified   INTEGER NOT NULL DEFAULT 0 CHECK (customer_notified IN (0, 1)),
    customer_phone      TEXT NOT NULL REFERENCES customer (phone),
    batch_id            INTEGER NOT NULL REFERENCES batch (batch_id),
    prescription_number TEXT UNIQUE REFERENCES prescription (number),
    CHECK (expires_at > created_at)
);

CREATE TABLE sale (
    number              TEXT PRIMARY KEY,
    sold_at             TEXT NOT NULL,
    payment_method      TEXT NOT NULL CHECK (payment_method IN ('готівка', 'картка')),
    total_kop           INTEGER NOT NULL CHECK (total_kop >= 0),
    personnel_number    TEXT NOT NULL REFERENCES pharmacist (personnel_number),
    customer_phone      TEXT REFERENCES customer (phone),
    prescription_number TEXT UNIQUE REFERENCES prescription (number)
);

CREATE TABLE sale_line (
    sale_number    TEXT NOT NULL REFERENCES sale (number) ON DELETE CASCADE,
    batch_id       INTEGER NOT NULL REFERENCES batch (batch_id),
    quantity       INTEGER NOT NULL CHECK (quantity >= 1),
    unit_price_kop INTEGER NOT NULL CHECK (unit_price_kop >= 0),
    PRIMARY KEY (sale_number, batch_id)
);

CREATE TABLE sequence (
    kind  TEXT PRIMARY KEY,
    value INTEGER NOT NULL CHECK (value >= 0)
);
