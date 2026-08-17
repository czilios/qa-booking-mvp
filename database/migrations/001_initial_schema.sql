-- ============================================================
-- Wrzosowo 159 Booking System
-- Migration: 001_initial_schema
-- Version: 0.1
--
-- Database compatibility:
-- MariaDB 10.1+
--
-- Purpose:
-- Initial database schema for the reservation management system.
-- ============================================================


-- ------------------------------------------------------------
-- 1. COTTAGES
-- ------------------------------------------------------------

CREATE TABLE cottages (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,

    name VARCHAR(50) NOT NULL,
    capacity TINYINT UNSIGNED NOT NULL DEFAULT 4,
    active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- 2. CUSTOMERS
-- ------------------------------------------------------------

CREATE TABLE customers (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,

    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(255) NULL,
    notes TEXT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    INDEX idx_customers_phone (phone)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- 3. RESERVATION SOURCES
-- ------------------------------------------------------------

CREATE TABLE reservation_sources (
    id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,

    code VARCHAR(30) NOT NULL,
    name VARCHAR(100) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (id),

    UNIQUE KEY uq_reservation_sources_code (code)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- 4. RESERVATIONS
-- ------------------------------------------------------------

CREATE TABLE reservations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    cottage_id INT UNSIGNED NOT NULL,
    customer_id INT UNSIGNED NULL,
    source_id SMALLINT UNSIGNED NOT NULL,

    check_in DATE NOT NULL,
    check_out DATE NOT NULL,

    guests_count TINYINT UNSIGNED NOT NULL,

    status ENUM(
        'PENDING',
        'CONFIRMED',
        'CANCELLED',
        'EXPIRED'
    ) NOT NULL DEFAULT 'PENDING',

    total_amount DECIMAL(10,2) NULL,
    deposit_amount DECIMAL(10,2) NULL,

    expires_at DATETIME NULL,

    notes TEXT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    CONSTRAINT fk_reservations_cottage
        FOREIGN KEY (cottage_id)
        REFERENCES cottages(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_reservations_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    CONSTRAINT fk_reservations_source
        FOREIGN KEY (source_id)
        REFERENCES reservation_sources(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_reservations_cottage_dates (
        cottage_id,
        check_in,
        check_out
    ),

    INDEX idx_reservations_status (status),
    INDEX idx_reservations_customer (customer_id),
    INDEX idx_reservations_source (source_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- 5. PAYMENTS
-- ------------------------------------------------------------

CREATE TABLE payments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    reservation_id BIGINT UNSIGNED NOT NULL,

    type ENUM(
        'DEPOSIT',
        'BALANCE'
    ) NOT NULL DEFAULT 'DEPOSIT',

    amount DECIMAL(10,2) NOT NULL,

    status ENUM(
        'UNPAID',
        'PAID',
        'FORFEITED',
        'REFUNDED'
    ) NOT NULL DEFAULT 'UNPAID',

    due_at DATETIME NULL,
    paid_at DATETIME NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    CONSTRAINT fk_payments_reservation
        FOREIGN KEY (reservation_id)
        REFERENCES reservations(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_payments_reservation (reservation_id),
    INDEX idx_payments_status (status)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- 6. BLOCKS
-- ------------------------------------------------------------

CREATE TABLE blocks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    cottage_id INT UNSIGNED NOT NULL,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    reason VARCHAR(255) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    CONSTRAINT fk_blocks_cottage
        FOREIGN KEY (cottage_id)
        REFERENCES cottages(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_blocks_cottage_dates (
        cottage_id,
        start_date,
        end_date
    )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- 7. INITIAL RESERVATION SOURCES
-- ------------------------------------------------------------

INSERT INTO reservation_sources
    (code, name)
VALUES
    ('DIRECT', 'Rezerwacja własna'),
    ('BOOKING', 'Booking.com'),
    ('AIRBNB', 'Airbnb'),
    ('BELVILLA', 'Belvilla'),
    ('NOCOWANIE', 'Nocowanie.pl'),
    ('OTONOCLEGI', 'OtoNoclegi.pl');


-- ------------------------------------------------------------
-- 8. INITIAL COTTAGES
-- ------------------------------------------------------------

INSERT INTO cottages
    (name, capacity)
VALUES
    ('Domek 1', 4),
    ('Domek 2', 4),
    ('Domek 3', 4),
    ('Domek 4', 4),
    ('Domek 5', 4),
    ('Domek 6', 4);