ALTER TABLE customers
    ADD COLUMN address TEXT NULL,
    MODIFY COLUMN phone VARCHAR(30) NULL,
    MODIFY COLUMN email VARCHAR(255) NULL,
    ADD CONSTRAINT chk_customers_contact CHECK (
        CHAR_LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), ' ', ''), CHAR(9), ''), CHAR(13), ''), CHAR(10), '')) > 0
        OR CHAR_LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(email, ''), ' ', ''), CHAR(9), ''), CHAR(13), ''), CHAR(10), '')) > 0
    );