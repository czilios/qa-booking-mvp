ALTER TABLE web_inquiries
    ADD COLUMN offered_cottage_id INT UNSIGNED NULL AFTER reservation_id,
    ADD COLUMN offered_check_in DATE NULL AFTER offered_cottage_id,
    ADD COLUMN offered_check_out DATE NULL AFTER offered_check_in,
    ADD COLUMN offered_total_amount DECIMAL(10,2) NULL AFTER offered_check_out,
    ADD COLUMN offered_deposit_amount DECIMAL(10,2) NULL AFTER offered_total_amount,
    ADD COLUMN message_sent_at DATETIME NULL AFTER offered_deposit_amount,
    ADD CONSTRAINT fk_web_inquiries_offered_cottage
        FOREIGN KEY (offered_cottage_id)
        REFERENCES cottages(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL;
