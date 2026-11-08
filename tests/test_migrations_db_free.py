from pathlib import Path

import pytest

from app import migration_runner as runner


MIGRATIONS = Path(__file__).resolve().parents[1] / "database" / "migrations"


def test_new_migration_contract():
    migration_007 = (MIGRATIONS / "007_bank_transactions_and_reservation_accounting.sql").read_text(encoding="utf-8")
    migration_008 = (MIGRATIONS / "008_payment_bank_transaction.sql").read_text(encoding="utf-8")
    migration_009 = (MIGRATIONS / "009_customer_contact.sql").read_text(encoding="utf-8")

    assert "REFERENCES reservation_sources(id)\n        ON DELETE RESTRICT" in migration_007
    assert "REFERENCES cottages(id)\n        ON DELETE SET NULL" in migration_007
    for column in (
        "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT",
        "transaction_date DATE NOT NULL",
        "source_id SMALLINT UNSIGNED NOT NULL",
        "cottage_id INT UNSIGNED NULL",
        "amount DECIMAL(10,2) NOT NULL",
        "description TEXT NULL",
        "notes TEXT NULL",
        "is_test_data BOOLEAN NOT NULL DEFAULT FALSE",
        "accounting_included BOOLEAN NOT NULL DEFAULT FALSE",
        "commission_amount DECIMAL(10,2) NULL",
        "invoice_number VARCHAR(100) NULL",
        "external_reservation_id VARCHAR(100) NULL",
    ):
        assert column in migration_007
    assert "invoice BOOLEAN NULL DEFAULT NULL" in migration_008
    assert "bank_transaction_id BIGINT UNSIGNED NULL DEFAULT NULL" in migration_008
    assert "INDEX idx_payments_bank_transaction (bank_transaction_id)" in migration_008
    assert "FOREIGN KEY (bank_transaction_id) REFERENCES bank_transactions(id)" in migration_008
    assert "ON DELETE SET NULL" in migration_008
    assert "UNIQUE" not in migration_008.upper()
    for column in ("ADD COLUMN address TEXT NULL", "MODIFY COLUMN phone VARCHAR(30) NULL", "MODIFY COLUMN email VARCHAR(255) NULL"):
        assert column in migration_009
    assert "CHECK (" in migration_009
    assert migration_009.count("CHAR_LENGTH(") == 2
    assert "COALESCE(phone, '')" in migration_009
    assert "COALESCE(email, '')" in migration_009
    assert "COALESCE(address, '')" not in migration_009
    assert migration_009.count("> 0") == 2
    assert migration_009.count(" OR ") == 1
    for column in ("phone", "email"):
        assert f"COALESCE({column}, '')" in migration_009
    for character in ("CHAR(9)", "CHAR(13)", "CHAR(10)"):
        assert migration_009.count(character) == 2


def _copy_migrations(destination):
    for source in MIGRATIONS.glob("*.sql"):
        (destination / source.name).write_bytes(source.read_bytes())


def test_migration_loader_accepts_future_contiguous_versions(monkeypatch, tmp_path):
    _copy_migrations(tmp_path)
    (tmp_path / "010_future_change.sql").write_text(
        "CREATE TABLE future_change_010 (id INT);", encoding="utf-8"
    )
    (tmp_path / "011_future_change.sql").write_text(
        "CREATE TABLE future_change_011 (id INT);", encoding="utf-8"
    )
    monkeypatch.setattr(runner, "MIGRATION_DIR", tmp_path)

    assert [migration[0] for migration in runner._load_migrations()] == list(range(1, 12))


def test_migration_loader_rejects_gaps_and_duplicate_versions(monkeypatch, tmp_path):
    gap_directory = tmp_path / "gap"
    gap_directory.mkdir()
    _copy_migrations(gap_directory)
    (gap_directory / "008_payment_bank_transaction.sql").unlink()
    monkeypatch.setattr(runner, "MIGRATION_DIR", gap_directory)
    with pytest.raises(runner.MigrationError, match="contiguous migration sequence"):
        runner._load_migrations()

    duplicate_directory = tmp_path / "duplicate"
    duplicate_directory.mkdir()
    _copy_migrations(duplicate_directory)
    (duplicate_directory / "009_duplicate_version.sql").write_text(
        "CREATE TABLE duplicate_version (id INT);", encoding="utf-8"
    )
    monkeypatch.setattr(runner, "MIGRATION_DIR", duplicate_directory)
    with pytest.raises(runner.MigrationError, match="contiguous migration sequence"):
        runner._load_migrations()


class FakeConnection:
    def __init__(self, *, database="test_booking", sources=None, history=None, objects=None, invalid_contacts=0, increment=1):
        self.database = database
        self.sources = sources if sources is not None else []
        self.history = history if history is not None else []
        self.objects = objects if objects is not None else set()
        self.invalid_contacts = invalid_contacts
        self.increment = increment
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.rows = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if query.startswith("SELECT DATABASE()"):
            self.rows = [(self.database, "10.11.6-MariaDB")]
        elif query.startswith("SELECT GET_LOCK") or query.startswith("SELECT RELEASE_LOCK"):
            self.rows = [(1,)]
        elif "information_schema.TABLES" in query:
            self.rows = [(name,) for name in self.objects]
        elif "information_schema.ROUTINES" in query or "information_schema.EVENTS" in query:
            self.rows = [(0,)]
        elif query.startswith("SELECT @@auto_increment"):
            self.rows = [(self.increment, 1)]
        elif query.startswith("SELECT version, filename"):
            self.rows = self.history[:]
        elif query.startswith("SELECT id, code"):
            self.rows = self.sources[:]
        elif query.startswith("SELECT COUNT(*) AS invalid_contacts"):
            self.rows = [(self.invalid_contacts,)]
        elif runner.SOURCE_INSERT.match(query):
            self.sources = list(enumerate(runner.SOURCE_CODES, 1))
        elif query.startswith("INSERT INTO schema_migrations"):
            self.history.append(params)

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def history(count=6):
    return [(version, name, checksum) for version, name, checksum, _ in runner._load_migrations()[:count]]


def run(connection, mode="existing", **kwargs):
    runner.run_migrations(connection, expected_database="test_booking", mode=mode, verified=True, **kwargs)


def test_fresh_migrations_check_sources_around_seed_and_record_order():
    connection = FakeConnection()
    run(connection, mode="fresh")
    assert [item[0] for item in connection.history] == list(range(1, 10))
    seed = next(index for index, (query, _) in enumerate(connection.executed) if runner.SOURCE_INSERT.match(query))
    assert connection.executed[seed - 1][0].startswith("SELECT id, code")
    assert connection.executed[seed + 1][0].startswith("SELECT id, code")
    assert connection.commits == 9


def test_existing_verified_history_runs_only_pending_migrations():
    connection = FakeConnection(sources=list(enumerate(runner.SOURCE_CODES, 1)), history=history(), objects={"schema_migrations", "reservation_sources"})
    run(connection)
    assert [item[0] for item in connection.history] == list(range(1, 10))
    assert connection.commits == 3


@pytest.mark.parametrize("connection,mode", [
    (FakeConnection(database="wrong"), "fresh"),
    (FakeConnection(objects={"customers"}), "fresh"),
    (FakeConnection(increment=2), "fresh"),
    (FakeConnection(objects={"reservation_sources"}), "existing"),
    (FakeConnection(history=history(5), objects={"schema_migrations", "reservation_sources"}), "existing"),
    (FakeConnection(history=history(), objects={"schema_migrations", "reservation_sources"}), "existing"),
    (FakeConnection(sources=list(enumerate(runner.SOURCE_CODES, 1)), history=history(), objects={"schema_migrations", "reservation_sources"}, invalid_contacts=1), "existing"),
])
def test_unverified_states_cause_no_ddl(connection, mode):
    with pytest.raises(runner.MigrationError):
        run(connection, mode=mode)
    assert not any(query.startswith(("CREATE TABLE", "ALTER TABLE")) for query, _ in connection.executed)


def test_sql_splitter_respects_literals_and_rejects_unsupported_syntax():
    assert runner.split_sql("-- comment;\nINSERT INTO x VALUES ('a;''b'); ALTER TABLE x ADD y INT;") == [
        "INSERT INTO x VALUES ('a;''b')", "ALTER TABLE x ADD y INT"
    ]
    for sql in ("INSERT INTO x VALUES ('oops);", "INSERT INTO x VALUES ('a\\'b');", "DELIMITER //", "/* comment */ CREATE TABLE x (a INT);"):
        with pytest.raises(runner.MigrationError):
            runner.split_sql(sql)


def test_explicit_verification_is_required_before_any_query():
    connection = FakeConnection()
    with pytest.raises(runner.MigrationError):
        runner.run_migrations(connection, expected_database="test_booking", mode="fresh", verified=False)
    assert connection.executed == []


@pytest.mark.parametrize("bad_history", [
    history()[:5] + [(6, "wrong.sql", history()[5][2])],
    history()[:5] + [(6, history()[5][1], "0" * 64)],
    history(9) + [(10, "010_unknown.sql", "0" * 64)],
])
def test_mismatched_history_is_rejected_without_ddl(bad_history):
    connection = FakeConnection(sources=list(enumerate(runner.SOURCE_CODES, 1)), history=bad_history, objects={"schema_migrations", "reservation_sources"})
    with pytest.raises(runner.MigrationError):
        run(connection)
    assert not any(query.startswith(("CREATE TABLE", "ALTER TABLE")) for query, _ in connection.executed)


def test_wrong_source_ids_are_rejected_without_ddl():
    sources = list(enumerate(runner.SOURCE_CODES, 1))
    sources[0], sources[1] = (1, "BOOKING"), (2, "DIRECT")
    connection = FakeConnection(sources=sources, history=history(), objects={"schema_migrations", "reservation_sources"})
    with pytest.raises(runner.MigrationError, match="mapping"):
        run(connection)
    assert not any(query.startswith(("CREATE TABLE", "ALTER TABLE")) for query, _ in connection.executed)


def test_bad_fresh_seed_is_detected_before_history_is_recorded():
    class WrongSeedConnection(FakeConnection):
        def execute(self, query, params=None):
            super().execute(query, params)
            if runner.SOURCE_INSERT.match(query):
                self.sources[0] = (1, "WRONG")

    connection = WrongSeedConnection()
    with pytest.raises(runner.MigrationError, match="mapping"):
        run(connection, mode="fresh")
    assert connection.history == []
    assert connection.rollbacks == 1
    assert connection.executed[-1][0].startswith("SELECT RELEASE_LOCK")


def test_preexisting_source_rows_abort_before_seed():
    connection = FakeConnection(sources=[(1, "DIRECT")])
    with pytest.raises(runner.MigrationError, match="empty before seeding"):
        run(connection, mode="fresh")
    assert not any(runner.SOURCE_INSERT.match(query) for query, _ in connection.executed)


def test_parser_failure_precedes_database_access(monkeypatch, tmp_path):
    for path in runner.MIGRATION_DIR.glob("*.sql"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / "009_customer_contact.sql").write_text("DELIMITER //", encoding="utf-8")
    monkeypatch.setattr(runner, "MIGRATION_DIR", tmp_path)
    connection = FakeConnection()
    with pytest.raises(runner.MigrationError):
        run(connection, mode="fresh")
    assert connection.executed == []


def test_dict_cursor_and_compatibility_prefixed_version():
    class DictConnection(FakeConnection):
        def execute(self, query, params=None):
            super().execute(query, params)
            if query.startswith("SELECT DATABASE()"):
                self.rows = [{"database_name": self.database, "server_version": "5.5.5-10.11.6-MariaDB"}]
            elif query.startswith("SELECT GET_LOCK"):
                self.rows = [{"acquired": 1}]
            elif "information_schema.TABLES" in query:
                self.rows = [{"object_name": name} for name in self.objects]
            elif query.startswith("SELECT version, filename"):
                self.rows = [dict(zip(("version", "filename", "checksum"), row)) for row in self.history]
            elif query.startswith("SELECT id, code"):
                self.rows = [dict(zip(("id", "code"), row)) for row in self.sources]

    connection = DictConnection(sources=list(enumerate(runner.SOURCE_CODES, 1)), history=history(9), objects={"schema_migrations", "reservation_sources"})
    run(connection)
    assert connection.commits == 0


def test_unavailable_lock_prevents_any_mutation():
    class LockedConnection(FakeConnection):
        def execute(self, query, params=None):
            super().execute(query, params)
            if query.startswith("SELECT GET_LOCK"):
                self.rows = [(0,)]

    connection = LockedConnection()
    with pytest.raises(runner.MigrationError, match="lock"):
        run(connection, mode="fresh")
    assert not any(query.startswith(("CREATE TABLE", "ALTER TABLE", "INSERT INTO")) for query, _ in connection.executed)


def test_failed_migration_rolls_back_and_releases_lock():
    class FailingConnection(FakeConnection):
        def execute(self, query, params=None):
            super().execute(query, params)
            if query.startswith("ALTER TABLE payments"):
                raise RuntimeError("DDL failed")

    connection = FailingConnection(sources=list(enumerate(runner.SOURCE_CODES, 1)), history=history(), objects={"schema_migrations", "reservation_sources"})
    with pytest.raises(RuntimeError, match="DDL failed"):
        run(connection)
    assert connection.rollbacks == 1
    assert [item[0] for item in connection.history] == list(range(1, 8))
    assert connection.executed[-1][0].startswith("SELECT RELEASE_LOCK")