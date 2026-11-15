import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app, get_api_write_connection, get_db_connection, rate_limiter
from app.auth import CSRF_COOKIE_NAME
from tests.conftest import TEST_CSRF_TOKEN


@pytest.fixture
def api_client(db_connection, monkeypatch, valid_operator_session_cookie):
    rate_limiter.clear()
    app.dependency_overrides[get_db_connection] = lambda: db_connection
    app.dependency_overrides[get_api_write_connection] = lambda: db_connection

    def run_test_transaction(operation, operation_name):
        try:
            result = operation(db_connection)
            db_connection.commit()
            return result
        except BaseException:
            db_connection.rollback()
            raise

    monkeypatch.setattr(
        main,
        "run_transaction_with_retry",
        run_test_transaction,
    )

    client = TestClient(app)
    client.cookies.set(*valid_operator_session_cookie)
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)
    client.headers["X-CSRF-Token"] = TEST_CSRF_TOKEN

    original_request = client.request

    def request_with_csrf(method, url, *args, **kwargs):
        method = method.upper()
        path = str(url).split("?", 1)[0]
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            if path.startswith("/api/") and path != "/api/inquiries":
                headers = dict(kwargs.get("headers") or {})
                headers.setdefault("X-CSRF-Token", TEST_CSRF_TOKEN)
                kwargs["headers"] = headers
            elif path.startswith("/ui/") or path == "/logout":
                data = kwargs.get("data")
                if isinstance(data, dict):
                    data = dict(data)
                    data.setdefault("csrf_token", TEST_CSRF_TOKEN)
                    kwargs["data"] = data
                elif data is None:
                    kwargs["data"] = {"csrf_token": TEST_CSRF_TOKEN}
                else:
                    if isinstance(data, (list, tuple)):
                        kwargs["data"] = list(data) + [("csrf_token", TEST_CSRF_TOKEN)]
        return original_request(method, url, *args, **kwargs)

    client.request = request_with_csrf
    yield client

    app.dependency_overrides.clear()
    rate_limiter.clear()
