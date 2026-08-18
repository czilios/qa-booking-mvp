from datetime import date
from fastapi.testclient import TestClient
from app.repositories.reservation_repository import ReservationRepository
from app.main import app, get_db_connection
import pytest

@pytest.fixture
def api_client(db_connection):
    app.dependency_overrides[get_db_connection] = lambda: db_connection

    yield TestClient(app)

    app.dependency_overrides.clear()

def test_get_availability_returns_200(api_client):
    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["check_in"] == "2027-07-10"
    assert body["check_out"] == "2027-07-17"
    assert body["cottages"] == [1, 2, 3, 4, 5, 6]


def test_get_availability_excludes_reserved_cottage(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 7, 12),
        check_out=date(2027, 7, 15),
        guests_count=2,
    )

    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert 1 not in body["cottages"]
    assert body["cottages"] == [2, 3, 4, 5, 6]

def test_get_availability_rejects_invalid_check_out(api_client):
    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-10",
            "check_out": "banana",
        },
    )

    assert response.status_code == 422

def test_get_availability_rejects_missing_check_out(api_client):
    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-10",
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["detail"][0]["loc"][-1] == "check_out"

def test_get_availability_rejects_invalid_date_range(api_client):
    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-17",
            "check_out": "2027-07-10",
        },
    )

    assert response.status_code == 400

def test_get_availability_rejects_same_check_in_and_check_out(
    api_client,
):
    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-17",
            "check_out": "2027-07-17",
        },
    )

    assert response.status_code == 400

def test_get_availability_excludes_blocked_cottage(
    db_connection,
    api_client,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO blocks (
                cottage_id,
                start_date,
                end_date,
                reason
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                1,
                date(2027, 7, 12),
                date(2027, 7, 15),
                "Maintenance",
            ),
        )

    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert 1 not in body["cottages"]
    assert body["cottages"] == [2, 3, 4, 5, 6]