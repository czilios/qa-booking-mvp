ALTER TABLE operator_sessions
    ADD COLUMN csrf_token_hash CHAR(64)
        CHARACTER SET ascii COLLATE ascii_bin NULL
        AFTER token_hash;
