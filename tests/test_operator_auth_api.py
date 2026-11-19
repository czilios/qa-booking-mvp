import secrets
from unittest.mock import Mock

import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from app import access_control, main
from app.auth import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME, hash_csrf_token, hash_operator_password


TEST_CSRF_TOKEN = "operator-auth-test-csrf-token"


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
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://testserver")
    main.app.state._state.pop("operator_password_hash", None)
    main.app.state._state.pop("session_cookie_secure", None)
    main.rate_limiter.clear()
    FakeSessionRepository.created = []
    return password


def test_login_creates_db_session_and_sets_secure_cookie(monkeypatch):
    password = _configure_auth(monkeypatch)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://testserver")
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr(main, "OperatorSessionRepository", FakeSessionRepository)

    client = TestClient(main.app, base_url="https://testserver")
    origin_headers = {"Origin": str(client.base_url).rstrip("/")}
    response = client.post(
        "/login",
        data={"login": "operator", "password": password, "next": "/ui"},
        follow_redirects=False,
        headers=origin_headers,
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
    assert len(saved["csrf_token_hash"]) == 64
    assert saved["csrf_token_hash"] not in response.headers.get_list("set-cookie")[1]
    csrf_cookie = next(
        cookie for cookie in response.headers.get_list("set-cookie")
        if "qa_booking_operator_csrf=" in cookie
    )
    assert "httponly" not in csrf_cookie.lower()
    assert "secure" in csrf_cookie.lower()


def test_authenticated_operator_panel_shows_csrf_protected_logout_form(monkeypatch):
    _configure_auth(monkeypatch, secure="false")
    session_connection = FakeConnection()
    ui_connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: session_connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    monkeypatch.setattr(main, "get_connection", lambda: ui_connection)

    class FakeCottageRepository:
        def __init__(self, connection):
            assert connection is ui_connection

        def get_active_cottage_ids(self):
            return [1]

    monkeypatch.setattr(main, "CottageRepository", FakeCottageRepository)
    client = TestClient(main.app)
    client.cookies.set(SESSION_COOKIE_NAME, secrets.token_urlsafe(32))
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)

    response = client.get("/ui")

    assert response.status_code == 200
    assert '<form method="post" action="/logout">' in response.text
    assert (
        f'<input type="hidden" name="csrf_token" value="{TEST_CSRF_TOKEN}">'
        in response.text
    )
    assert "Wyloguj" in response.text
    assert session_connection.closed
    assert ui_connection.closed


def test_invalid_credentials_have_the_same_generic_response(monkeypatch):
    password = _configure_auth(monkeypatch)
    client = TestClient(main.app)
    origin_headers = {"Origin": str(client.base_url).rstrip("/")}

    unknown_login = client.post(
        "/login",
        data={"login": "unknown", "password": password},
        headers=origin_headers,
    )
    wrong_password = client.post(
        "/login",
        data={"login": "operator", "password": secrets.token_urlsafe(32)},
        headers=origin_headers,
    )

    assert unknown_login.status_code == wrong_password.status_code == 401
    assert unknown_login.text == wrong_password.text
    assert "Nieprawidłowy login lub hasło." in unknown_login.text


def test_login_does_not_open_database_for_invalid_credentials(monkeypatch):
    _configure_auth(monkeypatch)
    connection_factory = Mock()
    monkeypatch.setattr(main, "get_connection", connection_factory)

    client = TestClient(main.app)
    response = client.post(
        "/login",
        data={"login": "operator", "password": secrets.token_urlsafe(32)},
        headers={"Origin": str(client.base_url).rstrip("/")},
    )

    assert response.status_code == 401
    connection_factory.assert_not_called()


def test_login_connection_acquisition_error_returns_503_without_rollback(monkeypatch):
    password = _configure_auth(monkeypatch)
    connection_factory = Mock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(main, "get_connection", connection_factory)

    client = TestClient(main.app)
    response = client.post(
        "/login",
        data={"login": "operator", "password": password},
        headers={"Origin": str(client.base_url).rstrip("/")},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Nie można teraz rozpocząć sesji."
    connection_factory.assert_called_once_with()


def test_login_rejects_missing_or_cross_origin_provenance(monkeypatch):
    password = _configure_auth(monkeypatch)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://booking.example")
    connection_factory = Mock()
    monkeypatch.setattr(main, "get_connection", connection_factory)
    client = TestClient(main.app, base_url="https://booking.example")

    missing_origin = client.post(
        "/login", data={"login": "operator", "password": password}
    )
    cross_origin = client.post(
        "/login",
        data={"login": "operator", "password": password},
        headers={"Origin": "https://attacker.example"},
    )

    assert missing_origin.status_code == 403
    assert cross_origin.status_code == 403
    connection_factory.assert_not_called()


def test_login_accepts_configured_origin_independent_of_request_host(monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://operator.example")
    monkeypatch.setattr(main, "get_connection", Mock())
    client = TestClient(main.app, base_url="http://untrusted.test")

    response = client.post(
        "/login",
        data={"login": "operator", "password": "invalid"},
        headers={
            "Origin": "https://operator.example",
            "Host": "attacker.example",
            "X-Forwarded-Host": "attacker.example",
            "X-Forwarded-Proto": "http",
        },
    )

    # Configured provenance passes; invalid credentials then produce the usual 401.
    assert response.status_code == 401
    main.get_connection.assert_not_called()


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://attacker.example", "Host": "attacker.example"},
        {
            "Origin": "https://operator.example.attacker.test",
            "Referer": "https://operator.example/panel",
        },
        {
            "Origin": "https://attacker.example",
            "X-Forwarded-Host": "attacker.example",
            "X-Forwarded-Proto": "https",
        },
        {"Origin": "null"},
        {"Origin": "not an origin"},
        {"Origin": "http://operator.example"},
        {"Origin": "https://operator.example:444"},
        {"Origin": "https://operator.example:0"},
        {"Referer": "https://attacker.example/form"},
    ],
)
def test_login_rejects_untrusted_provenance_regardless_of_host_headers(
    monkeypatch, headers
):
    password = _configure_auth(monkeypatch)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://operator.example:443")
    connection_factory = Mock()
    monkeypatch.setattr(main, "get_connection", connection_factory)
    client = TestClient(main.app, base_url="https://operator.example")

    response = client.post(
        "/login",
        data={"login": "operator", "password": password},
        headers=headers,
    )

    assert response.status_code == 403
    connection_factory.assert_not_called()


def test_login_uses_referer_when_origin_is_absent(monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://operator.example")
    monkeypatch.setattr(main, "get_connection", Mock())
    client = TestClient(main.app, base_url="http://untrusted.test")

    response = client.post(
        "/login",
        data={"login": "operator", "password": "invalid"},
        headers={"Referer": "https://operator.example/panel/login?next=%2Fui"},
    )

    assert response.status_code == 401
    main.get_connection.assert_not_called()


@pytest.mark.parametrize(
    "configuration",
    [None, "https://operator.example:", "https://operator.example/", "https://operator.example/panel"],
)
def test_login_fails_closed_for_missing_or_invalid_trusted_origin_configuration(
    monkeypatch, configuration
):
    password = _configure_auth(monkeypatch)
    if configuration is None:
        monkeypatch.delenv("CSRF_TRUSTED_ORIGINS")
    else:
        monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", configuration)
    connection_factory = Mock()
    monkeypatch.setattr(main, "get_connection", connection_factory)
    client = TestClient(main.app)

    response = client.post(
        "/login",
        data={"login": "operator", "password": password},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Login security configuration is unavailable."
    connection_factory.assert_not_called()


def test_logout_connection_acquisition_error_returns_503_without_rollback(monkeypatch):
    _configure_auth(monkeypatch)
    connection_factory = Mock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(main, "get_connection", connection_factory)
    access_connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: access_connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    client = TestClient(main.app)
    client.cookies.set(SESSION_COOKIE_NAME, secrets.token_urlsafe(32))
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)

    response = client.post(
        "/logout", data={"csrf_token": TEST_CSRF_TOKEN}, follow_redirects=False
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Nie można teraz zakończyć sesji."
    connection_factory.assert_called_once_with()


def test_login_attempts_are_limited_per_client_in_the_current_process(monkeypatch):
    _configure_auth(monkeypatch)
    client = TestClient(main.app)
    client.headers["Origin"] = str(client.base_url).rstrip("/")

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
    csrf_token = TEST_CSRF_TOKEN
    monkeypatch.setattr(access_control, "get_connection", lambda: FakeConnection())
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(csrf_token),
        },
    )
    monkeypatch.setattr(
        main,
        "authenticate_operator_session",
        lambda connection, token: {
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(csrf_token),
        },
    )
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    response = client.post(
        "/logout",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert revoked and revoked[0][0] is connection
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert any(
        "qa_booking_operator_csrf=" in cookie and "max-age=0" in cookie.lower()
        for cookie in response.headers.get_list("set-cookie")
    )
    assert connection.commits == 1
    assert connection.closed


def test_logout_uses_secure_cookie_value_validated_during_lifespan(monkeypatch):
    _configure_auth(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: FakeConnection())
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr(
        main,
        "authenticate_operator_session",
        lambda connection, token: {
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    monkeypatch.setattr(main, "revoke_operator_session", lambda connection, token: True)

    with TestClient(main.app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE_NAME, secrets.token_urlsafe(32))
        client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)
        # A later environment change must not alter the setting cached at startup.
        monkeypatch.setenv("APP_ENV", "local")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
        response = client.post(
            "/logout",
            data={"csrf_token": TEST_CSRF_TOKEN},
            follow_redirects=False,
        )

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
            headers={"Origin": str(client.base_url).rstrip("/")},
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
