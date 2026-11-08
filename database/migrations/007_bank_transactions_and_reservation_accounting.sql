CREATE TABLE bank_transactions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    transaction_date DATE NOT NULL,
    source_id SMALLINT UNSIGNED NOT NULL,
    cottage_id INT UNSIGNED NULL,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT NULL,
    notes TEXT NULL,
    is_test_data BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id),
    CONSTRAINT fk_bank_transactions_source
        FOREIGN KEY (source_id) REFERENCES reservation_sources(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_bank_transactions_cottage
        FOREIGN KEY (cottage_id) REFERENCES cottages(id)
        ON DELETE SET NULL,
    INDEX idx_bank_transactions_source (source_id),
    INDEX idx_bank_transactions_cottage (cottage_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

ALTER TABLE reservations
    ADD COLUMN accounting_included BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN commission_amount DECIMAL(10,2) NULL,
    ADD COLUMN invoice_number VARCHAR(100) NULL,
    ADD COLUMN external_reservation_id VARCHAR(100) NULL;