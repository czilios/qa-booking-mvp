ALTER TABLE web_inquiries
    ADD COLUMN reservation_id BIGINT UNSIGNED NULL AFTER status,
    ADD UNIQUE INDEX uq_web_inquiries_reservation_id (reservation_id),
    ADD CONSTRAINT fk_web_inquiries_reservation
        FOREIGN KEY (reservation_id)
        REFERENCES reservations(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL;
