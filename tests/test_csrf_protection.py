from unittest.mock import Mock

from fastapi.testclient import TestClient

from app import access_control, main
from app.auth import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    hash_csrf_token,
    hash_operator_password,
)


SESSION_TOKEN = "csrf-test-session-token-0000000000000000000000000000000000000000"
CSRF_TOKEN = "csrf-test-token-0000000000000000000000000000000000000000"
OTHER_CSRF_TOKEN = "other-session-token-0000000000000000000000000000000000000000"


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


def _authenticated_client(monkeypatch, *, expected_csrf=CSRF_TOKEN, root_path=""):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    auth_connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: auth_connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(expected_csrf),
        },
    )
    client = TestClient(main.app, root_path=root_path)
    client.cookies.set(SESSION_COOKIE_NAME, SESSION_TOKEN)
    client.cookies.set(CSRF_COOKIE_NAME, expected_csrf)
    return client, auth_connection


def test_api_write_requires_csrf_header_and_accepts_matching_session_token(monkeypatch):
    endpoint_connection = FakeConnection()
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_api_write_connection,
        lambda: endpoint_connection,
    )
    monkeypatch.setattr(main, "create_customer", lambda **kwargs: 9)

    class FakeCustomerRepository:
        def __init__(self, connection):
            assert connection is endpoint_connection

        def get_by_id(self, customer_id):
            return {"id": customer_id, "first_name": "Test"}

    monkeypatch.setattr(main, "CustomerRepository", FakeCustomerRepository)
    client, auth_connection = _authenticated_client(monkeypatch)
    payload = {"first_name": "Test", "last_name": "Operator"}

    missing = client.post("/customers", json=payload)
    invalid = client.post(
        "/customers", json=payload, headers={"X-CSRF-Token": "invalid"}
    )
    valid = client.post(
        "/customers", json=payload, headers={"X-CSRF-Token": CSRF_TOKEN}
    )

    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert valid.status_code == 201
    assert valid.json() == {"id": 9, "first_name": "Test"}
    assert auth_connection.commits == 3


def test_api_rejects_csrf_token_bound_to_another_session(monkeypatch):
    client, _ = _authenticated_client(monkeypatch, expected_csrf=CSRF_TOKEN)

    response = client.post(
        "/customers",
        json={"first_name": "Test", "last_name": "Operator"},
        headers={"X-CSRF-Token": OTHER_CSRF_TOKEN},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token is missing or invalid."}


def test_api_csrf_remains_enforced_with_root_path(monkeypatch):
    client, _ = _authenticated_client(monkeypatch, root_path="/api")

    missing = client.post(
        "/api/customers",
        json={"first_name": "Test", "last_name": "Operator"},
    )
    invalid = client.post(
        "/api/customers",
        json={"first_name": "Test", "last_name": "Operator"},
        headers={"X-CSRF-Token": "invalid"},
    )

    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert missing.json() == {"detail": "CSRF token is missing or invalid."}


def test_session_without_csrf_hash_must_authenticate_again(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda db_connection, token: {"id": 1, "operator_id": "operator"},
    )
    client = TestClient(main.app)
    client.cookies.set(SESSION_COOKIE_NAME, SESSION_TOKEN)

    response = client.get("/reservations/10")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_html_form_token_is_validated_and_request_body_remains_available(monkeypatch):
    endpoint_connection = FakeConnection()
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_db_connection,
        lambda: endpoint_connection,
    )
    updates = []

    class FakeInquiryRepository:
        def __init__(self, connection):
            assert connection is endpoint_connection

        def update_status(self, **kwargs):
            updates.append(kwargs)

    monkeypatch.setattr(main, "WebInquiryRepository", FakeInquiryRepository)
    client, _ = _authenticated_client(monkeypatch)

    response = client.post(
        "/ui/inquiries/12/status",
        data={"csrf_token": CSRF_TOKEN, "status": "IN_PROGRESS"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert updates == [{"inquiry_id": 12, "status": "IN_PROGRESS"}]
    assert endpoint_connection.commits == 1


def test_logout_requires_a_valid_csrf_token_and_then_revokes_session(monkeypatch):
    endpoint_connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: endpoint_connection)
    monkeypatch.setattr(
        main,
        "authenticate_operator_session",
        lambda connection, token: {"operator_id": "operator"},
    )
    revoked = []
    monkeypatch.setattr(
        main,
        "revoke_operator_session",
        lambda connection, token: revoked.append(token) or True,
    )
    client, _ = _authenticated_client(monkeypatch)

    missing = client.post("/logout", follow_redirects=False)
    invalid = client.post(
        "/logout", data={"csrf_token": OTHER_CSRF_TOKEN}, follow_redirects=False
    )
    valid = client.post(
        "/logout", data={"csrf_token": CSRF_TOKEN}, follow_redirects=False
    )

    assert missing.status_code == invalid.status_code == 403
    assert revoked == [SESSION_TOKEN]
    assert valid.status_code == 303
    assert valid.headers["location"] == "/login"


def test_authenticated_get_needs_no_submitted_csrf_token(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_customer",
        lambda **kwargs: {"id": kwargs["customer_id"], "first_name": "Test"},
    )
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_db_connection,
        lambda: FakeConnection(),
    )
    client, _ = _authenticated_client(monkeypatch)
    client.cookies.delete(CSRF_COOKIE_NAME)

    response = client.get("/customers/10")

    assert response.status_code == 200
    assert response.json()["id"] == 10


def test_operator_html_page_exposes_token_and_disables_caching(monkeypatch):
    ui_connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: ui_connection)

    class FakeCottageRepository:
        def __init__(self, connection):
            pass

        def get_active_cottage_ids(self):
            return [1]

    class FakeAvailability:
        def get_available_cottages(self, **kwargs):
            return [1]

    monkeypatch.setattr(main, "CottageRepository", FakeCottageRepository)
    monkeypatch.setattr(main, "AvailabilityService", lambda **kwargs: FakeAvailability())
    client, _ = _authenticated_client(monkeypatch)

    response = client.get(
        "/ui",
        params={
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "cottage_id": 1,
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert f'name="csrf-token" content="{CSRF_TOKEN}"' in response.text
    assert f'name="csrf_token" value="{CSRF_TOKEN}"' in response.text


def test_public_inquiry_post_remains_available_without_operator_csrf(monkeypatch):
    endpoint_connection = FakeConnection()
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_db_connection,
        lambda: endpoint_connection,
    )
    class FakeAvailability:
        def get_available_cottages(self, **kwargs):
            return []

    monkeypatch.setattr(main, "AvailabilityService", lambda **kwargs: FakeAvailability())

    class FakeInquiryRepository:
        def __init__(self, connection):
            pass

        def create(self, **kwargs):
            return 77

    monkeypatch.setattr(main, "WebInquiryRepository", FakeInquiryRepository)
    monkeypatch.setattr(access_control, "get_connection", Mock())
    main.rate_limiter.clear()
    client = TestClient(main.app)

    response = client.post(
        "/inquiries",
        json={
            "full_name": "Test Visitor",
            "phone": "+48600999111",
            "email": "visitor@example.com",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
            "consent": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == 77
    access_control.get_connection.assert_not_called()
    main.rate_limiter.clear()


def test_login_creates_csrf_session_without_preexisting_operator_session(monkeypatch):
    password = hash_operator_password("local-test-password")
    monkeypatch.setenv("OPERATOR_PASSWORD_HASH", password)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://testserver")
    main.app.state._state.pop("operator_password_hash", None)
    main.app.state._state.pop("session_cookie_secure", None)
    main.rate_limiter.clear()
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    created = []

    class FakeSessionRepository:
        def __init__(self, db_connection):
            pass

        def create(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(main, "OperatorSessionRepository", FakeSessionRepository)
    client = TestClient(main.app)
    assert SESSION_COOKIE_NAME not in client.cookies

    response = client.post(
        "/login",
        data={"login": "operator", "password": "local-test-password"},
        headers={"Origin": str(client.base_url).rstrip("/")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    csrf_cookie = next(
        cookie
        for cookie in response.headers.get_list("set-cookie")
        if f"{CSRF_COOKIE_NAME}=" in cookie
    )
    raw_token = csrf_cookie.split("=", 1)[1].split(";", 1)[0]
    assert created[0]["csrf_token_hash"] == hash_csrf_token(raw_token)
    assert raw_token not in str(created[0])
    assert response.headers["cache-control"] == "no-store"
