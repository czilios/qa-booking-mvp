CREATE TABLE operator_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    operator_id VARCHAR(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    last_activity_at DATETIME(6) NOT NULL,
    absolute_expires_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_operator_sessions_token_hash (token_hash),
    KEY idx_operator_sessions_absolute_expiry (absolute_expires_at),
    KEY idx_operator_sessions_idle_expiry (last_activity_at)
) ENGINE=InnoDB;
