CREATE TABLE web_inquiries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    full_name VARCHAR(200) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(255) NOT NULL,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    guests_count TINYINT UNSIGNED NOT NULL,
    preferred_cottage_id INT UNSIGNED NULL,
    message TEXT NULL,
    availability_found BOOLEAN NOT NULL,
    status ENUM(
        'NEW',
        'IN_PROGRESS',
        'CONVERTED',
        'REJECTED',
        'CLOSED'
    ) NOT NULL DEFAULT 'NEW',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_web_inquiries_preferred_cottage
        FOREIGN KEY (preferred_cottage_id)
        REFERENCES cottages(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    INDEX idx_web_inquiries_status_created (status, created_at),
    INDEX idx_web_inquiries_created_at (created_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
