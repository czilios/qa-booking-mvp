import pytest

from app.database import get_connection


@pytest.fixture
def db_connection():
    connection = get_connection()

    try:
        connection.begin()
        yield connection
        connection.rollback()
    finally:
        connection.close()