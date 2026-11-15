from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import main
from app.auth import CSRF_COOKIE_NAME
from tests.conftest import TEST_CSRF_TOKEN
from app.transaction_retry import TransactionOutcomeUnknown, TransactionRetryExhausted


class FakeConnection:
    def __init__(self):
        self.events = []

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.events.append("close")


def test_api_write_dependency_commits_success_and_closes(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)

    dependency = main.get_api_write_connection()
    assert next(dependency) is connection

    with pytest.raises(StopIteration):
        next(dependency)

    assert connection.events == ["commit", "close"]


def test_api_write_dependency_rolls_back_mid_operation_failure_and_closes(
    monkeypatch,
):
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)

    dependency = main.get_api_write_connection()
    assert next(dependency) is connection

    connection.events.append("first_write")
    connection.events.append("second_write_started")
    with pytest.raises(RuntimeError, match="second write failed"):
        dependency.throw(RuntimeError("second write failed"))

    assert connection.events == [
        "first_write",
        "second_write_started",
        "rollback",
        "close",
    ]
    assert "commit" not in connection.events


def test_api_write_dependency_rolls_back_if_commit_raises(monkeypatch):
    connection = FakeConnection()

    def fail_commit():
        connection.events.append("commit")
        raise RuntimeError("commit failed")

    connection.commit = fail_commit
    monkeypatch.setattr(main, "get_connection", lambda: connection)

    dependency = main.get_api_write_connection()
    next(dependency)
    with pytest.raises(RuntimeError, match="commit failed"):
        next(dependency)

    assert connection.events == ["commit", "rollback", "close"]


@pytest.mark.parametrize(
    "path, method",
    [
        ("/api/reservations", "POST"),
        ("/api/reservations/{reservation_id}", "PUT"),
        ("/api/reservations/{reservation_id}", "DELETE"),
        ("/api/payments", "POST"),
        ("/api/payments/{payment_id}/paid", "PUT"),
        ("/api/customers", "POST"),
        ("/api/customers/{customer_id}", "PUT"),
    ],
)
def test_crud_write_routes_use_transaction_dependency(path, method):
    route = next(
        route
        for route in main.app.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    )

    write_dependencies = [
        dependency
        for dependency in route.dependant.dependencies
        if dependency.call is main.get_api_write_connection
    ]
    if (path, method) in {
        ("/api/reservations", "POST"),
        ("/api/reservations/{reservation_id}", "PUT"),
    }:
        assert write_dependencies == []
    else:
        assert len(write_dependencies) == 1
        assert write_dependencies[0].scope == "function"


def test_api_write_dependency_opens_connection_only_after_being_requested(
    monkeypatch,
):
    connection = FakeConnection()
    connect = Mock(return_value=connection)
    monkeypatch.setattr(main, "get_connection", connect)

    assert connect.call_count == 0
    dependency = main.get_api_write_connection()
    assert connect.call_count == 0
    assert next(dependency) is connection
    connect.assert_called_once_with()
    dependency.close()


def test_write_dependency_commits_before_http_response_starts(
    monkeypatch, valid_operator_session_cookie
):
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)

    def run_operation(operation, operation_name):
        result = operation(connection)
        connection.commit()
        return result

    monkeypatch.setattr(main, "run_transaction_with_retry", run_operation)

    def create_reservation(**kwargs):
        connection.events.append("operation")
        return 42

    monkeypatch.setattr(main, "create_reservation", create_reservation)

    class ResponseStartProbe:
        def __init__(self, app):
            self.app = app
            self.events_at_response_start = None

        async def __call__(self, scope, receive, send):
            async def capture_send(message):
                if message["type"] == "http.response.start":
                    self.events_at_response_start = list(connection.events)
                await send(message)

            await self.app(scope, receive, capture_send)

    probe = ResponseStartProbe(main.app)
    client = TestClient(probe)
    client.cookies.set(*valid_operator_session_cookie)
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)
    client.headers["X-CSRF-Token"] = TEST_CSRF_TOKEN
    response = client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-07-20",
            "check_out": "2027-07-27",
            "guests_count": 2,
        },
    )

    assert response.status_code == 201
    assert probe.events_at_response_start == ["operation", "commit"]


def test_http_exception_after_write_rolls_back_without_commit(
    monkeypatch, valid_operator_session_cookie
):
    connection = FakeConnection()
    monkeypatch.setattr(main, "get_connection", lambda: connection)

    def run_operation(operation, operation_name):
        try:
            return operation(connection)
        except BaseException:
            connection.rollback()
            raise

    monkeypatch.setattr(main, "run_transaction_with_retry", run_operation)

    def fail_after_write(**kwargs):
        connection.events.append("operation")
        raise HTTPException(status_code=409, detail="operation rejected")

    monkeypatch.setattr(main, "create_reservation", fail_after_write)

    client = TestClient(main.app)
    client.cookies.set(*valid_operator_session_cookie)
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)
    client.headers["X-CSRF-Token"] = TEST_CSRF_TOKEN
    response = client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-07-20",
            "check_out": "2027-07-27",
            "guests_count": 2,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "operation rejected"
    assert connection.events == ["operation", "rollback"]


@pytest.mark.parametrize(
    "method, path, request_data",
    [
        (
            "post",
            "/api/reservations",
            {
                "json": {
                    "cottage_id": 1,
                    "source_id": 1,
                    "check_in": "2027-07-20",
                    "check_out": "2027-07-27",
                    "guests_count": 2,
                }
            },
        ),
        (
            "put",
            "/api/reservations/123",
            {
                "json": {
                    "cottage_id": 1,
                    "source_id": 1,
                    "check_in": "2027-07-20",
                    "check_out": "2027-07-27",
                    "guests_count": 2,
                }
            },
        ),
        (
            "post",
            "/ui/reservations",
            {
                "data": {
                    "cottage_id": 1,
                    "check_in": "2027-07-20",
                    "check_out": "2027-07-27",
                    "first_name": "Test",
                    "last_name": "Retry",
                    "phone": "+48123456789",
                    "guests_count": 2,
                    "csrf_token": TEST_CSRF_TOKEN,
                }
            },
        ),
        (
            "post",
            "/ui/inquiries/123/accept",
            {"data": {"csrf_token": TEST_CSRF_TOKEN}},
        ),
    ],
)
@pytest.mark.parametrize("error_kind", ["exhausted", "unknown_outcome"])
def test_all_retry_endpoints_map_database_errors_to_safe_503(
    monkeypatch,
    valid_operator_session_cookie,
    method,
    path,
    request_data,
    error_kind,
):
    if error_kind == "exhausted":
        runner_error = TransactionRetryExhausted(
            error_code=1213,
            operation_name="test_reservation_operation",
            attempts=3,
            correlation_id="test-correlation",
        )
        expected_detail = "Temporary database contention prevented completion. Try again later."
    else:
        runner_error = TransactionOutcomeUnknown(
            error_code=2013,
            operation_name="test_reservation_operation",
            stage="commit",
            correlation_id="test-correlation",
        )
        expected_detail = (
            "The operation outcome could not be confirmed. "
            "Check its current status before submitting it again."
        )

    monkeypatch.setattr(
        main,
        "run_transaction_with_retry",
        Mock(side_effect=runner_error),
    )

    client = TestClient(main.app)
    client.cookies.set(*valid_operator_session_cookie)
    client.cookies.set(CSRF_COOKIE_NAME, TEST_CSRF_TOKEN)
    client.headers["X-CSRF-Token"] = TEST_CSRF_TOKEN
    response = getattr(client, method)(path, **request_data)

    assert response.status_code == 503
    assert response.json()["detail"] == expected_detail
    assert "1213" not in response.text
    assert "2013" not in response.text
    assert "SQL" not in response.text
