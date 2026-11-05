from unittest.mock import Mock

import pytest

from app.database import get_test_connection, get_test_db_config
from tests.conftest import _apply_test_data_default


VALID_TEST_ENV = {
    "TEST_MODE": "true",
    "TEST_DB_HOST": "127.0.0.1",
    "TEST_DB_PORT": "3307",
    "TEST_DB_NAME": "wrzosowo_booking_test",
    "TEST_DB_USER": "booking_test",
    "TEST_DB_PASSWORD": "test-password",
}


def test_valid_test_database_configuration_is_accepted():
    config = get_test_db_config(VALID_TEST_ENV)

    assert config.host == "127.0.0.1"
    assert config.port == 3307
    assert config.database == "wrzosowo_booking_test"
    assert config.user == "booking_test"
    assert config.password == "test-password"


def test_missing_test_configuration_is_rejected():
    with pytest.raises(RuntimeError, match="Missing test database configuration") as exc:
        get_test_db_config({"TEST_MODE": "true"})

    assert "TEST_DB_HOST" in str(exc.value)
    assert "TEST_DB_PASSWORD" in str(exc.value)


def test_wrong_database_name_is_rejected():
    environ = {**VALID_TEST_ENV, "TEST_DB_NAME": "wrzosowo_booking_dev"}

    with pytest.raises(RuntimeError, match="must be exactly 'wrzosowo_booking_test'"):
        get_test_db_config(environ)


def test_development_configuration_is_not_used_as_a_fallback():
    environ = {
        "TEST_MODE": "true",
        "DB_HOST": "dev-db.example.test",
        "DB_PORT": "3306",
        "DB_NAME": "wrzosowo_booking_dev",
        "DB_USER": "dev-user",
        "DB_PASSWORD": "dev-password",
    }

    with pytest.raises(RuntimeError, match="Missing test database configuration"):
        get_test_db_config(environ)


def test_disabled_test_mode_is_rejected():
    environ = {**VALID_TEST_ENV, "TEST_MODE": "false"}

    with pytest.raises(RuntimeError, match="Set TEST_MODE=true explicitly"):
        get_test_db_config(environ)


def test_invalid_configuration_fails_before_opening_a_connection(monkeypatch):
    connect = Mock()
    monkeypatch.setattr("app.database.pymysql.connect", connect)

    with pytest.raises(RuntimeError, match="Missing test database configuration"):
        get_test_connection({"TEST_MODE": "true"})

    connect.assert_not_called()


def test_valid_test_connection_uses_only_validated_test_settings(monkeypatch):
    connect = Mock(return_value=object())
    monkeypatch.setattr("app.database.pymysql.connect", connect)

    connection = get_test_connection(VALID_TEST_ENV)

    assert connection is connect.return_value
    connect.assert_called_once()
    kwargs = connect.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 3307
    assert kwargs["database"] == "wrzosowo_booking_test"
    assert kwargs["user"] == "booking_test"
    assert kwargs["password"] == "test-password"
    assert kwargs["autocommit"] is False


def test_requesting_db_connection_without_test_configuration_fails_before_connecting(
    monkeypatch,
    request,
):
    for name in (
        "TEST_MODE",
        "TEST_DB_HOST",
        "TEST_DB_PORT",
        "TEST_DB_NAME",
        "TEST_DB_USER",
        "TEST_DB_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("DB_HOST", "dev-db.example.test")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_NAME", "wrzosowo_booking_dev")
    monkeypatch.setenv("DB_USER", "dev-user")
    monkeypatch.setenv("DB_PASSWORD", "dev-password")

    connect = Mock()
    monkeypatch.setattr("app.database.pymysql.connect", connect)

    with pytest.raises(RuntimeError, match="Set TEST_MODE=true explicitly"):
        request.getfixturevalue("db_connection")

    connect.assert_not_called()


def test_test_reservation_default_marks_omitted_flag_as_test_data():
    kwargs = {}

    result = _apply_test_data_default(kwargs, is_test_data_explicit=False)

    assert result["is_test_data"] is True


def test_test_reservation_default_preserves_explicit_false():
    kwargs = {"is_test_data": False}

    result = _apply_test_data_default(kwargs, is_test_data_explicit=True)

    assert result["is_test_data"] is False


def test_test_reservation_default_preserves_explicit_true():
    kwargs = {"is_test_data": True}

    result = _apply_test_data_default(kwargs, is_test_data_explicit=True)

    assert result["is_test_data"] is True