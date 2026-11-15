import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app, get_api_write_connection, get_db_connection, rate_limiter


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
    yield client

    app.dependency_overrides.clear()
    rate_limiter.clear()
