import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db_connection


@pytest.fixture
def api_client(db_connection):
    app.dependency_overrides[get_db_connection] = lambda: db_connection

    yield TestClient(app)

    app.dependency_overrides.clear()