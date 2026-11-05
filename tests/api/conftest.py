import pytest
from fastapi.testclient import TestClient

from app.main import app, get_api_write_connection, get_db_connection, rate_limiter


@pytest.fixture
def api_client(db_connection):
    rate_limiter.clear()
    app.dependency_overrides[get_db_connection] = lambda: db_connection
    app.dependency_overrides[get_api_write_connection] = lambda: db_connection

    yield TestClient(app)

    app.dependency_overrides.clear()
    rate_limiter.clear()
