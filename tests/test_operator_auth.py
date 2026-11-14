from datetime import datetime, timedelta
import secrets

import pytest
from argon2 import PasswordHasher, Type

from app.auth import (
    AuthConfigurationError,
    SESSION_ABSOLUTE_TIMEOUT,
    SESSION_IDLE_TIMEOUT,
    MIN_ARGON2_MEMORY_COST,
    MIN_ARGON2_PARALLELISM,
    MIN_ARGON2_TIME_COST,
    create_operator_session,
    hash_operator_password,
    hash_session_token,
    load_operator_password_hash,
    safe_login_redirect,
    session_cookie_secure,
    session_idle_cutoff,
    verify_operator_credentials,
)
from app.repositories.operator_session_repository import OperatorSessionRepository


def test_password_hash_uses_argon2id_and_verifies_without_storing_plaintext():
    password = secrets.token_urlsafe(32)
    password_hash = hash_operator_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password not in password_hash
    assert verify_operator_credentials("operator", password, password_hash)


def test_unknown_login_and_wrong_password_are_rejected():
    password = secrets.token_urlsafe(32)
    password_hash = hash_operator_password(password)

    assert not verify_operator_credentials("unknown", password, password_hash)
    assert not verify_operator_credentials("operator", secrets.token_urlsafe(32), password_hash)


def test_password_hash_configuration_requires_a_valid_argon2id_hash():
    with pytest.raises(AuthConfigurationError, match="is missing"):
        load_operator_password_hash({})

    with pytest.raises(AuthConfigurationError, match="valid Argon2id"):
        load_operator_password_hash({"OPERATOR_PASSWORD_HASH": "not-a-hash"})

    other_algorithm_hash = PasswordHasher(type=Type.I).hash(secrets.token_urlsafe(32))
    with pytest.raises(AuthConfigurationError, match="must use Argon2id"):
        load_operator_password_hash({"OPERATOR_PASSWORD_HASH": other_algorithm_hash})


def test_password_hash_configuration_accepts_argon2id_at_minimum_parameters():
    password = secrets.token_urlsafe(32)
    acceptable_hash = PasswordHasher(
        type=Type.ID,
        memory_cost=MIN_ARGON2_MEMORY_COST,
        time_cost=MIN_ARGON2_TIME_COST,
        parallelism=MIN_ARGON2_PARALLELISM,
    ).hash(password)

    assert load_operator_password_hash({"OPERATOR_PASSWORD_HASH": acceptable_hash}) == acceptable_hash


@pytest.mark.parametrize(
    ("memory_cost", "time_cost", "parallelism"),
    [
        (MIN_ARGON2_MEMORY_COST - 1, MIN_ARGON2_TIME_COST, MIN_ARGON2_PARALLELISM),
        (MIN_ARGON2_MEMORY_COST, MIN_ARGON2_TIME_COST - 1, MIN_ARGON2_PARALLELISM),
        (MIN_ARGON2_MEMORY_COST, MIN_ARGON2_TIME_COST, MIN_ARGON2_PARALLELISM - 1),
    ],
)
def test_password_hash_configuration_rejects_hash_below_any_minimum_parameter(
    memory_cost, time_cost, parallelism
):
    weak_hash = PasswordHasher(
        type=Type.ID,
        memory_cost=memory_cost,
        time_cost=time_cost,
        parallelism=parallelism,
    ).hash(secrets.token_urlsafe(32))

    with pytest.raises(AuthConfigurationError, match="minimum Argon2id parameters"):
        load_operator_password_hash({"OPERATOR_PASSWORD_HASH": weak_hash})


def test_session_token_is_random_and_only_its_digest_is_persisted():
    session = create_operator_session(now=datetime(2026, 1, 1))

    assert len(session.token) >= 40
    assert session.token_hash == hash_session_token(session.token)
    assert session.token_hash != session.token
    assert len(session.token_hash) == 64
    assert session.operator_id == "operator"
    assert session.last_activity_at == session.created_at
    assert session.absolute_expires_at == session.created_at + SESSION_ABSOLUTE_TIMEOUT


def test_session_idle_cutoff_uses_approved_timeout():
    now = datetime(2026, 1, 1, 12, 0)

    assert SESSION_IDLE_TIMEOUT == timedelta(minutes=30)
    assert session_idle_cutoff(now) == datetime(2026, 1, 1, 11, 30)


@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        ("/ui", "/ui"),
        ("/ui/reservations/12?x=1", "/ui/reservations/12?x=1"),
        ("https://attacker.invalid/", "/ui"),
        ("//attacker.invalid/", "/ui"),
        ("/\\attacker.invalid", "/ui"),
    ],
)
def test_login_redirect_rejects_open_redirects(destination, expected):
    assert safe_login_redirect(destination) == expected


def test_secure_cookie_defaults_on_and_cannot_be_disabled_in_production():
    assert session_cookie_secure({"APP_ENV": "production"}) is True
    assert session_cookie_secure(
        {"APP_ENV": "local", "SESSION_COOKIE_SECURE": "false"}
    ) is False
    assert session_cookie_secure(
        {"APP_ENV": "test", "SESSION_COOKIE_SECURE": "false"}
    ) is False
    with pytest.raises(AuthConfigurationError, match="local/test"):
        session_cookie_secure(
            {"APP_ENV": "production", "SESSION_COOKIE_SECURE": "false"}
        )
    with pytest.raises(AuthConfigurationError, match="local/test"):
        session_cookie_secure({"APP_ENV": "development", "SESSION_COOKIE_SECURE": "false"})


@pytest.mark.parametrize("environ", [{}, {"APP_ENV": "staging"}, {"APP_ENV": ""}])
def test_cookie_configuration_requires_an_explicit_known_environment(environ):
    with pytest.raises(AuthConfigurationError, match="APP_ENV"):
        session_cookie_secure(environ)


def test_invalid_secure_cookie_setting_is_rejected():
    with pytest.raises(AuthConfigurationError, match="must be a boolean"):
        session_cookie_secure({"APP_ENV": "production", "SESSION_COOKIE_SECURE": "sometimes"})


class _InterleavedCursor:
    def __init__(self, session, events):
        self.session = session
        self.events = events
        self.rowcount = 1
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params):
        self.executed.append((query, params))
        if "FOR UPDATE" in query:
            self.events.append("select_for_update")

    def fetchone(self):
        # A later request updated the locked row before this older request
        # acquired SELECT FOR UPDATE.
        self.events.append("lock_acquired")
        return self.session.copy()


class _InterleavedConnection:
    def __init__(self, session, events):
        self.cursor_instance = _InterleavedCursor(session, events)

    def cursor(self):
        return self.cursor_instance


def test_concurrent_stale_activity_update_never_moves_timestamp_backwards():
    newer_activity = datetime(2026, 1, 1, 12, 0, 10)
    older_request_time = datetime(2026, 1, 1, 12, 0, 5)
    session = {
        "id": 7,
        "operator_id": "operator",
        "created_at": datetime(2026, 1, 1, 11, 0),
        "last_activity_at": newer_activity,
        "absolute_expires_at": datetime(2026, 1, 1, 23, 0),
        "revoked_at": None,
    }
    events = []
    connection = _InterleavedConnection(session, events)

    def clock_after_lock():
        events.append("clock")
        return older_request_time

    result = OperatorSessionRepository(connection).touch_if_active(
        token_hash="a" * 64,
        clock=clock_after_lock,
        idle_timeout=SESSION_IDLE_TIMEOUT,
    )

    update_sql, update_params = connection.cursor_instance.executed[1]
    assert "FOR UPDATE" in connection.cursor_instance.executed[0][0]
    assert "GREATEST(last_activity_at, %s)" in update_sql
    assert update_params[0] == older_request_time
    assert result["last_activity_at"] == newer_activity
    assert events == ["select_for_update", "lock_acquired", "clock"]


@pytest.mark.parametrize(
    ("last_activity_at", "absolute_expires_at", "checked_at"),
    [
        (
            datetime(2026, 1, 1, 11, 0),
            datetime(2026, 1, 1, 23, 0),
            datetime(2026, 1, 1, 11, 30, 1),
        ),
        (
            datetime(2026, 1, 1, 12, 0),
            datetime(2026, 1, 1, 12, 30),
            datetime(2026, 1, 1, 12, 30, 1),
        ),
    ],
)
def test_session_expiring_during_lock_wait_is_rejected(
    last_activity_at, absolute_expires_at, checked_at
):
    events = []
    session = {
        "id": 8,
        "operator_id": "operator",
        "created_at": datetime(2026, 1, 1, 0, 0),
        "last_activity_at": last_activity_at,
        "absolute_expires_at": absolute_expires_at,
        "revoked_at": None,
    }
    connection = _InterleavedConnection(session, events)

    def clock_after_lock():
        events.append("clock")
        return checked_at

    result = OperatorSessionRepository(connection).touch_if_active(
        token_hash="b" * 64,
        clock=clock_after_lock,
        idle_timeout=SESSION_IDLE_TIMEOUT,
    )

    assert result is None
    assert len(connection.cursor_instance.executed) == 1
    assert events == ["select_for_update", "lock_acquired", "clock"]
