from fastapi.testclient import TestClient

from app.main import app, get_db_connection


def test_create_reservation_returns_201(api_client):
    response = api_client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-07-20",
            "check_out": "2027-07-27",
            "guests_count": 2,
        },
    )
    print(response.json())

    assert response.status_code == 201

from datetime import date

from app.repositories.reservation_repository import ReservationRepository


def test_create_reservation_rejects_unavailable_cottage(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 7, 10),
        check_out=date(2027, 7, 17),
        guests_count=2,
    )

    response = api_client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-07-12",
            "check_out": "2027-07-15",
            "guests_count": 2,
        },
    )

    assert response.status_code == 409
def test_create_reservation_rejects_zero_guests(api_client):
    response = api_client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-10",
            "check_out": "2027-08-17",
            "guests_count": 0,
        },
    )

    assert response.status_code == 422

def test_create_reservation_rejects_too_many_guests(
    api_client,
):
    response = api_client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-10",
            "check_out": "2027-08-17",
            "guests_count": 5,
        },
    )

    assert response.status_code == 409
def test_create_reservation_rejects_negative_guests(api_client):
    response = api_client.post(
        "/api/reservations",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-10",
            "check_out": "2027-08-17",
            "guests_count": -1,
        },
    )

    assert response.status_code == 422