from datetime import date

from app.repositories.customer_repository import CustomerRepository
from app.repositories.reservation_repository import ReservationRepository

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

def test_create_reservation_with_customer_returns_201(
    api_client,
    db_connection,
):
    customer_repository = CustomerRepository(db_connection)

    customer_id = customer_repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
        email="jan@example.com",
    )

    response = api_client.post(
        "/api/reservations",
        json={
            "customer_id": customer_id,
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2028-06-10",
            "check_out": "2028-06-17",
            "guests_count": 2,
        },
    )

    assert response.status_code == 201

    reservation_id = response.json()

    reservation_repository = ReservationRepository(db_connection)

    reservation = reservation_repository.get_by_id(reservation_id)

    assert reservation["customer_id"] == customer_id

def test_get_reservation_returns_customer_id(
    api_client,
    db_connection,
):
    customer_repository = CustomerRepository(db_connection)

    customer_id = customer_repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
    )

    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        customer_id=customer_id,
        source_id=1,
        check_in=date(2028, 7, 10),
        check_out=date(2028, 7, 17),
        guests_count=2,
    )

    response = api_client.get(
        f"/api/reservations/{reservation_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["customer_id"] == customer_id

def test_get_reservation_returns_200(
    api_client,
    db_connection,
):
    customer_repository = CustomerRepository(db_connection)

    customer_id = customer_repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
        email="jan@example.com",
    )

    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        customer_id=customer_id,
        source_id=1,
        check_in=date(2028, 7, 10),
        check_out=date(2028, 7, 17),
        guests_count=2,
    )

    response = api_client.get(
        f"/api/reservations/{reservation_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == reservation_id
    assert data["customer_id"] == customer_id
    assert data["cottage_id"] == 1
    assert data["source_id"] == 1
    assert data["check_in"] == "2028-07-10"
    assert data["check_out"] == "2028-07-17"
    assert data["guests_count"] == 2