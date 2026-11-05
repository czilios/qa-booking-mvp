import os
from collections.abc import Mapping
from dataclasses import dataclass

import pymysql
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@dataclass(frozen=True)
class TestDatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


def get_test_db_config(
    environ: Mapping[str, str] | None = None,
) -> TestDatabaseConfig:
    values = os.environ if environ is None else environ

    if values.get("TEST_MODE", "").strip().lower() != "true":
        raise RuntimeError(
            "Automated DB tests are disabled. Set TEST_MODE=true explicitly "
            "to enable the dedicated test database."
        )

    required_variables = (
        "TEST_DB_HOST",
        "TEST_DB_PORT",
        "TEST_DB_NAME",
        "TEST_DB_USER",
        "TEST_DB_PASSWORD",
    )
    missing_variables = [
        name for name in required_variables if not values.get(name, "").strip()
    ]
    if missing_variables:
        raise RuntimeError(
            "Missing test database configuration: "
            + ", ".join(missing_variables)
            + ". Set TEST_DB_HOST, TEST_DB_PORT, TEST_DB_NAME, "
            "TEST_DB_USER, and TEST_DB_PASSWORD; DB_* values are never used "
            "as a fallback."
        )

    database = values["TEST_DB_NAME"]
    if database != "wrzosowo_booking_test":
        raise RuntimeError(
            "TEST_DB_NAME must be exactly 'wrzosowo_booking_test'; "
            f"received {database!r}. Refusing to connect."
        )

    try:
        port = int(values["TEST_DB_PORT"])
    except ValueError as exc:
        raise RuntimeError("TEST_DB_PORT must be an integer from 1 to 65535.") from exc

    if not 1 <= port <= 65535:
        raise RuntimeError("TEST_DB_PORT must be an integer from 1 to 65535.")

    return TestDatabaseConfig(
        host=values["TEST_DB_HOST"].strip(),
        port=port,
        database=database,
        user=values["TEST_DB_USER"].strip(),
        password=values["TEST_DB_PASSWORD"],
    )


def get_test_connection(
    environ: Mapping[str, str] | None = None,
):
    config = get_test_db_config(environ)
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
