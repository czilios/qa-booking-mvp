import hashlib
import re
from pathlib import Path


MIGRATION_DIR = Path(__file__).resolve().parents[1] / "database" / "migrations"
SOURCE_CODES = ("DIRECT", "BOOKING", "AIRBNB", "BELVILLA", "NOCOWANIE", "OTONOCLEGI")
FILENAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")
SOURCE_INSERT = re.compile(r"^INSERT\s+INTO\s+reservation_sources\b", re.IGNORECASE)
SOURCE_VALUE = re.compile(r"\(\s*'((?:[^']|'')*)'\s*,\s*'(?:[^']|'')*'\s*\)")


class MigrationError(RuntimeError):
    pass


def split_sql(script):
    statements = []
    buffer = []
    quoted = False
    index = 0
    while index < len(script):
        character = script[index]
        following = script[index:index + 2]
        if quoted:
            if character == "\\":
                raise MigrationError("Backslash escapes are not supported in SQL strings")
            buffer.append(character)
            if character == "'":
                if index + 1 < len(script) and script[index + 1] == "'":
                    buffer.append("'")
                    index += 1
                else:
                    quoted = False
        elif character == "'":
            quoted = True
            buffer.append(character)
        elif following == "--" and (index + 2 == len(script) or script[index + 2].isspace()):
            end = script.find("\n", index + 2)
            if end == -1:
                break
            buffer.append("\n")
            index = end
        elif following in ("/*", "--") or character in ('"', "`", "#", "\\"):
            raise MigrationError("Unsupported SQL syntax")
        elif character == ";":
            statement = "".join(buffer).strip()
            if statement:
                if not re.match(r"^(CREATE\s+TABLE|ALTER\s+TABLE|INSERT\s+INTO)\s+", statement, re.IGNORECASE):
                    raise MigrationError("Unsupported SQL statement")
                statements.append(statement)
            buffer = []
        else:
            buffer.append(character)
        index += 1
    if quoted or "".join(buffer).strip():
        raise MigrationError("Unterminated SQL statement or string")
    return statements


def _load_migrations():
    migrations = []
    for path in sorted(MIGRATION_DIR.glob("*.sql")):
        match = FILENAME.fullmatch(path.name)
        if not match:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        content = path.read_bytes()
        statements = split_sql(content.decode("utf-8"))
        if not statements:
            raise MigrationError(f"Empty migration: {path.name}")
        migrations.append((int(match.group(1)), path.name, hashlib.sha256(content).hexdigest(), statements))
    versions = [migration[0] for migration in migrations]
    if not migrations or versions != list(range(1, len(migrations) + 1)):
        raise MigrationError("Expected a contiguous migration sequence starting at 001")
    source_seeds = [statement for statement in migrations[0][3] if SOURCE_INSERT.match(statement)]
    if len(source_seeds) != 1:
        raise MigrationError("Migration 001 must contain exactly one reservation source seed")
    seed = source_seeds[0]
    if not re.match(r"^INSERT\s+INTO\s+reservation_sources\s*\(\s*code\s*,\s*name\s*\)\s*VALUES\s*", seed, re.IGNORECASE):
        raise MigrationError("Unrecognized reservation source seed")
    values = re.split(r"\bVALUES\b", seed, maxsplit=1, flags=re.IGNORECASE)[1]
    if tuple(match.group(1).replace("''", "'") for match in SOURCE_VALUE.finditer(values)) != SOURCE_CODES:
        raise MigrationError("Migration 001 source seed does not match required IDs 1-6")
    if SOURCE_VALUE.sub("", values).replace(",", "").strip():
        raise MigrationError("Unrecognized reservation source seed values")
    return migrations


def _value(row, key, index=0):
    return row[key] if isinstance(row, dict) else row[index]


def _check_sources(cursor, empty=False):
    cursor.execute("SELECT id, code FROM reservation_sources ORDER BY id")
    rows = cursor.fetchall()
    if empty:
        if rows:
            raise MigrationError("Reservation sources must be empty before seeding")
        return
    actual = {int(_value(row, "id", 0)): _value(row, "code", 1) for row in rows}
    if any(actual.get(index) != code for index, code in enumerate(SOURCE_CODES, 1)):
        raise MigrationError("Reservation source IDs 1-6 do not match the required mapping")


def _check_customer_contacts(cursor):
    def normalized(column):
        return f"REPLACE(REPLACE(REPLACE(REPLACE(COALESCE({column}, ''), ' ', ''), CHAR(9), ''), CHAR(13), ''), CHAR(10), '')"

    cursor.execute(
        "SELECT COUNT(*) AS invalid_contacts FROM customers WHERE "
        f"CHAR_LENGTH({normalized('phone')}) = 0 AND CHAR_LENGTH({normalized('email')}) = 0"
    )
    if _value(cursor.fetchone(), "invalid_contacts"):
        raise MigrationError("Customers without phone or email must be repaired before migration 009")


def run_migrations(connection, *, expected_database, mode, verified):
    if verified is not True or mode not in ("fresh", "existing"):
        raise MigrationError("Explicit verification and a fresh or existing mode are required")
    if not isinstance(expected_database, str) or not expected_database or expected_database.lower() in {
        "mysql", "information_schema", "performance_schema", "sys"
    }:
        raise MigrationError("A non-system database name is required")
    migrations = _load_migrations()
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE() AS database_name, VERSION() AS server_version")
        row = cursor.fetchone()
        if _value(row, "database_name", 0) != expected_database:
            raise MigrationError("Connected database does not match expected_database")
        server_version = _value(row, "server_version", 1)
        version_match = re.search(r"(\d+)\.(\d+)\.(\d+)[^\d]*mariadb", server_version, re.IGNORECASE)
        if not version_match or tuple(map(int, version_match.groups())) < (10, 2, 1):
            raise MigrationError("MariaDB 10.2.1 or later is required for enforced CHECK constraints")
        lock_name = "migrations:" + hashlib.sha256(expected_database.encode("utf-8")).hexdigest()[:48]
        cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (lock_name,))
        if _value(cursor.fetchone(), "acquired") != 1:
            raise MigrationError("Could not acquire migration lock")
        try:
            cursor.execute("SELECT TABLE_NAME AS object_name FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")
            objects = {_value(row, "object_name") for row in cursor.fetchall()}
            if mode == "fresh":
                if objects:
                    raise MigrationError("Fresh mode requires a database without tables or views")
                cursor.execute("SELECT COUNT(*) AS object_count FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE()")
                if _value(cursor.fetchone(), "object_count"):
                    raise MigrationError("Fresh mode requires a database without routines")
                cursor.execute("SELECT COUNT(*) AS object_count FROM information_schema.EVENTS WHERE EVENT_SCHEMA = DATABASE()")
                if _value(cursor.fetchone(), "object_count"):
                    raise MigrationError("Fresh mode requires a database without events")
                cursor.execute("SELECT @@auto_increment_increment AS increment_value, @@auto_increment_offset AS offset_value")
                row = cursor.fetchone()
                if (_value(row, "increment_value", 0), _value(row, "offset_value", 1)) != (1, 1):
                    raise MigrationError("Fresh mode requires auto-increment increment and offset of 1")
                cursor.execute(
                    "CREATE TABLE schema_migrations (version INT UNSIGNED NOT NULL PRIMARY KEY, "
                    "filename VARCHAR(255) NOT NULL, checksum CHAR(64) NOT NULL, "
                    "installed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB"
                )
                applied = []
            else:
                if "schema_migrations" not in objects or "reservation_sources" not in objects:
                    raise MigrationError("Existing database requires a migration history and source table; no baseline is created")
                cursor.execute("SELECT version, filename, checksum FROM schema_migrations ORDER BY version")
                applied = [(_value(row, "version", 0), _value(row, "filename", 1), _value(row, "checksum", 2)) for row in cursor.fetchall()]
                expected_history = [(version, name, checksum) for version, name, checksum, _ in migrations[:len(applied)]]
                if len(applied) < 6 or applied != expected_history:
                    raise MigrationError("Migration history is incomplete or does not match migration files")
                _check_sources(cursor)
                if len(applied) < 9:
                    _check_customer_contacts(cursor)
            for version, filename, checksum, statements in migrations[len(applied):]:
                for statement in statements:
                    is_source_seed = version == 1 and SOURCE_INSERT.match(statement)
                    if is_source_seed:
                        _check_sources(cursor, empty=True)
                    cursor.execute(statement)
                    if is_source_seed:
                        _check_sources(cursor)
                cursor.execute(
                    "INSERT INTO schema_migrations (version, filename, checksum) VALUES (%s, %s, %s)",
                    (version, filename, checksum),
                )
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s) AS released", (lock_name,))