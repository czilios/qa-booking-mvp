from unittest.mock import Mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute
import pytest

from app import access_control, main
from app.access_control import API_ROUTE_PATHS, OperatorAccessMiddleware
from app.auth import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME, hash_csrf_token


TEST_CSRF_TOKEN = "access-control-test-csrf-token"


def _set_operator_cookies(client, session_token="valid-session-token"):
    client.cookies.set(SESSION_COOKIE_NAME, session_token)
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)


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


def _operator_test_app():
    application = FastAPI()

    @application.get("/customers/{customer_id}")
    def private_api(request: Request, customer_id: int):
        return {"operator_id": request.state.operator["operator_id"]}

    @application.get("/ui/private")
    def private_ui(request: Request):
        return {"operator_id": request.state.operator["operator_id"]}

    application.add_middleware(
        OperatorAccessMiddleware,
        routes=application.router.routes,
    )
    return application


def test_anonymous_api_gets_json_401_without_database_access(monkeypatch):
    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)

    response = TestClient(main.app).get("/reservations/123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
    connection_factory.assert_not_called()


def test_anonymous_api_gets_json_401_with_root_path_without_database_access(monkeypatch):
    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)

    response = TestClient(main.app, root_path="/api").get("/api/reservations/123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("GET", "/customers/123", {}),
        (
            "POST",
            "/customers",
            {"json": {"first_name": "Test", "last_name": "Operator"}},
        ),
    ],
)
def test_anonymous_requests_to_operational_api_routes_get_json_401(
    method, path, kwargs, monkeypatch
):
    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)

    response = TestClient(main.app).request(method, path, **kwargs)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Authentication required."}
    connection_factory.assert_not_called()


def test_every_registered_operational_api_route_is_operator_only():
    public_routes = {
        ("GET", "/availability"),
        ("POST", "/inquiries"),
    }

    registered_api_paths = {
        route.path
        for route in main.app.router.routes
        if isinstance(route, APIRoute)
        and route.path not in {"/", "/health", "/login", "/logout"}
        and not route.path.startswith("/ui")
        and route.path not in {
            "/docs",
            "/docs/oauth2-redirect",
            "/openapi.json",
            "/redoc",
        }
    }
    assert registered_api_paths == API_ROUTE_PATHS

    api_routes = [
        route
        for route in main.app.router.routes
        if isinstance(route, APIRoute) and route.path in API_ROUTE_PATHS
    ]

    assert api_routes
    for route in api_routes:
        for method in route.methods or set():
            pair = (method, route.path)
            if pair in public_routes:
                category = access_control.classify_access(route.path, method)
                assert category is access_control.AccessCategory.PUBLIC
            else:
                category = access_control.classify_access(route.path, method)
                assert category is access_control.AccessCategory.OPERATOR_ONLY


def test_no_registered_operator_ui_route_is_accidentally_public():
    ui_routes = [
        route
        for route in main.app.router.routes
        if isinstance(route, APIRoute) and route.path.startswith("/ui")
    ]

    assert ui_routes
    for route in ui_routes:
        for method in route.methods or set():
            assert access_control.classify_access(
                route.path, method
            ) is access_control.AccessCategory.OPERATOR_ONLY


def test_valid_operator_session_reaches_actual_api_endpoint(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda db_connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    monkeypatch.setattr(
        main,
        "get_customer",
        lambda **kwargs: {"id": kwargs["customer_id"], "first_name": "Test"},
    )
    main.app.dependency_overrides[main.get_db_connection] = lambda: FakeConnection()
    client = TestClient(main.app)
    _set_operator_cookies(client)

    try:
        response = client.get("/customers/123")
    finally:
        main.app.dependency_overrides.pop(main.get_db_connection, None)

    assert response.status_code == 200
    assert response.json() == {"id": 123, "first_name": "Test"}
    assert connection.commits == 1
    assert connection.closed


def test_anonymous_ui_redirects_to_login(monkeypatch):
    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)

    response = TestClient(main.app).get("/ui", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")
    connection_factory.assert_not_called()


@pytest.mark.parametrize("path", ["/ui", "/ui/reports/overall", "/ui/inquiries"])
def test_anonymous_operator_ui_routes_redirect_to_login(path, monkeypatch):
    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)

    response = TestClient(main.app).get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    ("root_path", "ui_path", "url_prefix"),
    [("", "/ui", ""), ("/api", "/api/ui", "/api")],
)
def test_valid_session_allows_actual_operator_ui_view(
    monkeypatch, root_path, ui_path, url_prefix
):
    session_connection = FakeConnection()
    ui_connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: session_connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda db_connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    monkeypatch.setattr(main, "get_connection", lambda: ui_connection)

    class FakeCottageRepository:
        def __init__(self, db_connection):
            assert db_connection is ui_connection

        def get_active_cottage_ids(self):
            return [1]

    monkeypatch.setattr(main, "CottageRepository", FakeCottageRepository)
    client = TestClient(main.app, root_path=root_path)
    _set_operator_cookies(client)

    response = client.get(ui_path)

    assert response.status_code == 200
    assert "Dostępność" in response.text
    assert f'href="{url_prefix}/ui"' in response.text
    assert f'action="{url_prefix}/logout"' in response.text
    assert session_connection.commits == 1
    assert session_connection.closed
    assert ui_connection.closed


def test_invalid_session_and_verification_error_deny_actual_operator_ui(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda db_connection, token: None,
    )
    client = TestClient(main.app)
    _set_operator_cookies(client, "expired-session-token")

    invalid_session = client.get("/ui", follow_redirects=False)
    assert invalid_session.status_code == 303
    assert invalid_session.headers["location"].startswith("/login?next=")

    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        Mock(side_effect=RuntimeError("private verification detail")),
    )
    verification_error = client.get("/ui", follow_redirects=False)

    assert verification_error.status_code == 503
    assert "private verification detail" not in verification_error.text
    assert connection.rollbacks == 1
    assert connection.closed


def test_valid_session_allows_operator_api_and_ui(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda db_connection, token: {
            "id": 1,
            "operator_id": "operator",
            "csrf_token_hash": hash_csrf_token(TEST_CSRF_TOKEN),
        },
    )
    client = TestClient(_operator_test_app())
    _set_operator_cookies(client)

    api_response = client.get("/customers/123")
    ui_response = client.get("/ui/private")

    assert api_response.status_code == 200
    assert api_response.json() == {"operator_id": "operator"}
    assert ui_response.status_code == 200
    assert ui_response.json() == {"operator_id": "operator"}
    assert connection.commits == 2
    assert connection.closed


def test_invalid_session_is_denied_for_api_and_ui(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        lambda db_connection, token: None,
    )
    client = TestClient(_operator_test_app())
    _set_operator_cookies(client, "expired-session-token")

    api_response = client.get("/customers/123")
    ui_response = client.get("/ui/private", follow_redirects=False)

    assert api_response.status_code == 401
    assert ui_response.status_code == 303
    assert ui_response.headers["location"].startswith("/login?next=")
    assert connection.commits == 2
    assert connection.closed


def test_session_verification_database_error_fails_closed(monkeypatch):
    monkeypatch.setattr(
        access_control,
        "get_connection",
        Mock(side_effect=RuntimeError("database detail must not be returned")),
    )
    client = TestClient(main.app)
    _set_operator_cookies(client, "session-token")

    response = client.get("/reservations/123")

    assert response.status_code == 503
    assert "database detail" not in response.text


def test_session_authenticator_error_rolls_back_and_fails_closed(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", lambda: connection)
    monkeypatch.setattr(
        access_control,
        "authenticate_operator_session",
        Mock(side_effect=RuntimeError("session verification detail")),
    )
    client = TestClient(main.app)
    _set_operator_cookies(client, "session-token")

    response = client.get("/reservations/123")

    assert response.status_code == 503
    assert "session verification detail" not in response.text
    assert connection.rollbacks == 1
    assert connection.closed


def test_unknown_route_remains_404_and_wrong_method_remains_405():
    client = TestClient(main.app)

    unknown = client.get("/not-a-real-route")
    wrong_method = client.post("/reservations/123")
    prefixed_client = TestClient(main.app, root_path="/api")
    prefixed_unknown = prefixed_client.get("/api/not-a-real-route")
    prefixed_wrong_method = prefixed_client.post("/api/reservations/123")

    assert unknown.status_code == 404
    assert wrong_method.status_code == 405
    assert prefixed_unknown.status_code == 404
    assert prefixed_wrong_method.status_code == 405


def test_authentication_exceptions_remain_accessible(monkeypatch):
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://testserver")
    monkeypatch.setattr(main, "_auth_configuration", lambda request: ("hash", False))
    monkeypatch.setattr(main, "verify_operator_credentials", lambda *args: False)
    monkeypatch.setattr(main, "_session_cookie_secure", lambda request: False)
    main.rate_limiter.clear()
    client = TestClient(main.app)

    login_page = client.get("/login")
    login_attempt = client.post(
        "/login",
        data={"login": "operator", "password": "bad"},
        headers={"Origin": str(client.base_url).rstrip("/")},
    )

    assert login_page.status_code == 200
    assert login_attempt.status_code == 401
    main.rate_limiter.clear()


def test_login_page_is_accessible_with_root_path(monkeypatch):
    monkeypatch.setattr(main, "_auth_configuration", lambda request: ("hash", False))

    response = TestClient(main.app, root_path="/api").get("/api/login")

    assert response.status_code == 200
    assert "Zaloguj" in response.text
    assert 'action="/api/login"' in response.text


def test_login_post_is_accessible_with_root_path(monkeypatch):
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://testserver")
    monkeypatch.setattr(main, "_auth_configuration", lambda request: ("hash", False))
    monkeypatch.setattr(main, "verify_operator_credentials", lambda *args: False)
    main.rate_limiter.clear()

    response = TestClient(main.app, root_path="/api").post(
        "/api/login",
        data={"login": "operator", "password": "invalid"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 401
    assert "Nieprawidłowy login lub hasło." in response.text
    assert "Authentication required." not in response.text
    main.rate_limiter.clear()


def test_operator_ui_stays_protected_with_root_path(monkeypatch):
    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)

    response = TestClient(main.app, root_path="/api").get(
        "/api/ui", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/api/login?next=")
    connection_factory.assert_not_called()


def test_public_endpoints_are_not_checked_for_operator_session(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(access_control, "get_connection", Mock())

    class FakeAvailability:
        def get_available_cottages(self, **kwargs):
            return [1]

    monkeypatch.setattr(main, "AvailabilityService", lambda **kwargs: FakeAvailability())

    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_db_connection,
        lambda: connection,
    )
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_availability_service,
        lambda: FakeAvailability(),
    )

    class FakeInquiryRepository:
        def __init__(self, db_connection):
            self.connection = db_connection

        def create(self, **kwargs):
            return 77

    monkeypatch.setattr(main, "WebInquiryRepository", FakeInquiryRepository)
    main.rate_limiter.clear()
    clients = [
        (TestClient(main.app), ""),
        (TestClient(main.app, root_path="/api"), "/api"),
    ]
    for client, prefix in clients:
        availability = client.get(
            f"{prefix}/availability",
            params={"check_in": "2050-07-10", "check_out": "2050-07-17"},
        )
        inquiry = client.post(
            f"{prefix}/inquiries",
            json={
                "full_name": "Test Operator Policy",
                "phone": "+48600999111",
                "email": "policy@example.com",
                "check_in": "2050-07-10",
                "check_out": "2050-07-17",
                "guests_count": 2,
                "consent": True,
            },
        )

        assert availability.status_code == 200
        assert inquiry.status_code == 201
        assert inquiry.json()["id"] == 77
    access_control.get_connection.assert_not_called()
    assert connection.commits == 2
    main.rate_limiter.clear()


def test_openapi_uses_relative_paths_and_root_path_server():
    local_schema = TestClient(main.app).get("/openapi.json").json()
    prefixed_client = TestClient(main.app, root_path="/api")
    prefixed_schema = prefixed_client.get("/api/openapi.json").json()

    assert "/availability" in local_schema["paths"]
    assert "/api/availability" not in local_schema["paths"]
    assert "servers" not in local_schema or local_schema["servers"] == []
    assert "/availability" in prefixed_schema["paths"]
    assert "/api/availability" not in prefixed_schema["paths"]
    assert prefixed_schema["servers"] == [{"url": "/api"}]

    docs = prefixed_client.get("/api/docs")
    assert docs.status_code == 200
    assert "/api/openapi.json" in docs.text


def test_root_health_and_cors_preflight_are_technical(monkeypatch):
    if not main.cors_origins:
        pytest.skip("No CORS origins are configured in this test environment")

    connection_factory = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(access_control, "get_connection", connection_factory)
    client = TestClient(main.app)

    root = client.get("/")
    health = client.get("/health")
    static = client.get("/static/styles.css")
    preflight = client.options(
        "/reservations/123",
        headers={
            "Origin": main.cors_origins[0],
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )

    assert root.status_code == 200
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert static.status_code == 200
    if main._api_docs_enabled:
        assert client.get("/docs").status_code == 200
        assert client.get("/docs/oauth2-redirect").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == main.cors_origins[0]
    assert "PUT" in preflight.headers["access-control-allow-methods"]
    assert "x-csrf-token" in preflight.headers["access-control-allow-headers"].lower()
    connection_factory.assert_not_called()
