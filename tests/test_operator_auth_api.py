import secrets
from unittest.mock import Mock

import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from app import main
from app.auth import SESSION_COOKIE_NAME, hash_operator_password


class FakeConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakeSessionRepository:
    created = []

    def __init__(self, connection):
        self.connection = connection

    def create(self, **values):
        self.created.append(values)
        return 1


def _configure_auth(monkeypatch, *, secure="true"):
    password = secrets.token_urlsafe(32)
    monkeypatch.setenv("OPERATOR_PASSWORD_HASH", hash_operator_password(password))
    monkeypatch.setenv("SESSION_COOKIE_SECURE", secure)
    monkeypatch.setenv("APP_ENV", "test")
    main.app.state.__dict__.pop("operator_password_hash", None)
    main.app.state.__dict__.pop("session_cookie_secure", None)
    main.rate_limiter.clear()
    FakeSessionRepository.created = []
    return password


def test_login_creates_db_session_and_sets_secure_cookie(monkeypatch):
    password = _configure_auth(monkeypatch)
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr(main, "OperatorSessionRepository", FakeSessionRepository)

    client = TestClient(main.app, base_url="https://testserver")
    response = client.post(
        "/login",
        data={"login": "operator", "password": password, "next": "/ui"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "max-age=43200" in cookie
    assert connection.commits == 1
    assert connection.closed
    assert len(FakeSessionRepository.created) == 1
    saved = FakeSessionRepository.created[0]
    assert len(saved["token_hash"]) == 64
    assert saved["token_hash"] not in response.headers["set-cookie"]
    assert saved["operator_id"] == "operator"


def test_invalid_credentials_have_the_same_generic_response(monkeypatch):
    password = _configure_auth(monkeypatch)
    client = TestClient(main.app)

    unknown_login = client.post(
        "/login",
        data={"login": "unknown", "password": password},
    )
    wrong_password = client.post(
        "/login",
        data={"login": "operator", "password": secrets.token_urlsafe(32)},
    )

    assert unknown_login.status_code == wrong_password.status_code == 401
    assert unknown_login.text == wrong_password.text
    assert "Nieprawidłowy login lub hasło." in unknown_login.text


def test_login_does_not_open_database_for_invalid_credentials(monkeypatch):
    _configure_auth(monkeypatch)
    connection_factory = Mock()
    monkeypatch.setattr(main, "get_connection", connection_factory)

    response = TestClient(main.app).post(
        "/login",
        data={"login": "operator", "password": secrets.token_urlsafe(32)},
    )

    assert response.status_code == 401
    connection_factory.assert_not_called()


def test_login_connection_acquisition_error_returns_503_without_rollback(monkeypatch):
    password = _configure_auth(monkeypatch)
    connection_factory = Mock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(main, "get_connection", connection_factory)

    response = TestClient(main.app).post(
        "/login",
        data={"login": "operator", "password": password},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Nie można teraz rozpocząć sesji."
    connection_factory.assert_called_once_with()


def test_logout_connection_acquisition_error_returns_503_without_rollback(monkeypatch):
    _configure_auth(monkeypatch)
    connection_factory = Mock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(main, "get_connection", connection_factory)
    client = TestClient(main.app)
    client.cookies.set(SESSION_COOKIE_NAME, secrets.token_urlsafe(32))

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 503
    assert response.json()["detail"] == "Nie można teraz zakończyć sesji."
    connection_factory.assert_called_once_with()


def test_login_attempts_are_limited_per_client_in_the_current_process(monkeypatch):
    _configure_auth(monkeypatch)
    client = TestClient(main.app)

    responses = [
        client.post(
            "/login",
            data={"login": "operator", "password": secrets.token_urlsafe(32)},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401] * 5 + [429]


def test_logout_revokes_session_and_clears_cookie(monkeypatch):
    _configure_auth(monkeypatch)
    connection = FakeConnection()
    revoked = []
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr(
        main,
        "authenticate_operator_session",
        lambda connection, token: {"operator_id": "operator"},
    )
    monkeypatch.setattr(
        main,
        "revoke_operator_session",
        lambda connection, token: revoked.append((connection, token)) or True,
    )

    client = TestClient(main.app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE_NAME, secrets.token_urlsafe(32))
    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert revoked and revoked[0][0] is connection
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert connection.commits == 1
    assert connection.closed


def test_logout_uses_secure_cookie_value_validated_during_lifespan(monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr(
        main,
        "authenticate_operator_session",
        lambda connection, token: {"operator_id": "operator"},
    )
    monkeypatch.setattr(main, "revoke_operator_session", lambda connection, token: True)

    with TestClient(main.app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE_NAME, secrets.token_urlsafe(32))
        # A later environment change must not alter the setting cached at startup.
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
        response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert "secure" in response.headers["set-cookie"].lower()


def test_login_rollback_failure_does_not_mask_original_error_or_log_messages(
    monkeypatch, caplog
):
    password = _configure_auth(monkeypatch)

    class BrokenConnection(FakeConnection):
        def commit(self):
            raise RuntimeError("database secret detail")

        def rollback(self):
            raise RuntimeError("rollback secret detail")

        def close(self):
            self.closed = True
            raise RuntimeError("close secret detail")

    connection = BrokenConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr(main, "OperatorSessionRepository", FakeSessionRepository)

    with TestClient(main.app) as client:
        response = client.post(
            "/login",
            data={"login": "operator", "password": password},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Nie można teraz rozpocząć sesji."
    assert connection.closed
    assert "database secret detail" not in caplog.text
    assert "rollback secret detail" not in caplog.text
    assert "close secret detail" not in caplog.text


def test_production_startup_rejects_disabled_secure_cookie(monkeypatch):
    _configure_auth(monkeypatch, secure="false")
    monkeypatch.setenv("APP_ENV", "production")

    from app.auth import AuthConfigurationError

    with pytest.raises(AuthConfigurationError, match="local/test"):
        with TestClient(main.app):
            pass


def test_startup_rejects_ambiguous_app_environment(monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.setenv("APP_ENV", "staging")

    from app.auth import AuthConfigurationError

    with pytest.raises(AuthConfigurationError, match="APP_ENV"):
        with TestClient(main.app):
            pass


def test_startup_rejects_missing_password_hash(monkeypatch):
    monkeypatch.delenv("OPERATOR_PASSWORD_HASH", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("APP_ENV", "test")

    from app.auth import AuthConfigurationError

    try:
        with TestClient(main.app):
            pass
    except AuthConfigurationError:
        return
    raise AssertionError("Application startup accepted a missing operator hash")


def test_configuration_rejects_argon2i_hash(monkeypatch):
    main.rate_limiter.clear()
    wrong_type_hash = PasswordHasher(type=Type.I).hash(secrets.token_urlsafe(32))
    monkeypatch.setenv("OPERATOR_PASSWORD_HASH", wrong_type_hash)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")

    from app.auth import AuthConfigurationError

    try:
        with TestClient(main.app):
            pass
    except AuthConfigurationError:
        return
    raise AssertionError("Application startup accepted a non-Argon2id hash")
