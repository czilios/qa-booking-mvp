-- Migration: 002_add_reservation_test_data_flag
-- Add explicit classification for non-production reservation records.

ALTER TABLE reservations
    ADD COLUMN is_test_data BOOLEAN NOT NULL DEFAULT FALSE
    AFTER status;
