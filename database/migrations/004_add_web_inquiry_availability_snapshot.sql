ALTER TABLE web_inquiries
    ADD COLUMN available_cottage_ids VARCHAR(100) NULL
    AFTER availability_found;
