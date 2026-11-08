ALTER TABLE payments
    ADD COLUMN invoice BOOLEAN NULL DEFAULT NULL,
    ADD COLUMN bank_transaction_id BIGINT UNSIGNED NULL DEFAULT NULL,
    ADD INDEX idx_payments_bank_transaction (bank_transaction_id),
    ADD CONSTRAINT fk_payments_bank_transaction
        FOREIGN KEY (bank_transaction_id) REFERENCES bank_transactions(id)
        ON DELETE SET NULL;