from datetime import date

from app.repositories.customer_repository import CustomerRepository
from app.repositories.reservation_repository import ReservationRepository

from app.main import app
from app.database import get_connection

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
            "check_in": "2031-09-10",
            "check_out": "2031-09-17",
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
        check_in=date(2030, 7, 10),
        check_out=date(2030, 7, 17),
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
    assert data["check_in"] == "2030-07-10"
    assert data["check_out"] == "2030-07-17"
    assert data["guests_count"] == 2

def test_create_ui_reservation_returns_303(
    api_client,
    created_reservation_cleanup,
):
    phone = "+48600111222"

    response = api_client.post(
        "/ui/reservations",
        data={
            "cottage_id": 1,
            "check_in": "2029-06-10",
            "check_out": "2029-06-17",
            "phone": phone,
            "guests_count": 2,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    connection = get_connection()

    try:
        customer_repository = CustomerRepository(connection)

        customer = customer_repository.get_by_phone(phone)

        assert customer is not None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM reservations
                WHERE customer_id = %s
                  AND cottage_id = %s
                  AND check_in = %s
                  AND check_out = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    customer["id"],
                    1,
                    "2029-06-10",
                    "2029-06-17",
                ),
            )

            reservation = cursor.fetchone()

        assert reservation is not None

        assert (f"reservation_created={reservation['id']}"
                in response.headers["location"]
                )

        created_reservation_cleanup["reservation_ids"].append(
            reservation["id"]
        )
        created_reservation_cleanup["customer_ids"].append(
            customer["id"]
        )

    finally:
        connection.close()

def test_create_ui_reservation_persists_data(
    api_client,
    created_reservation_cleanup,
):
    phone = "+48600111223"

    response = api_client.post(
        "/ui/reservations",
        data={
            "cottage_id": 1,
            "check_in": "2029-06-10",
            "check_out": "2029-06-17",
            "phone": phone,
            "guests_count": 2,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    connection = get_connection()

    try:
        customer_repository = CustomerRepository(connection)

        customer = customer_repository.get_by_phone(phone)

        assert customer is not None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM reservations
                WHERE cottage_id = %s
                  AND customer_id = %s
                  AND check_in = %s
                  AND check_out = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    1,
                    customer["id"],
                    "2029-06-10",
                    "2029-06-17",
                ),
            )

            reservation = cursor.fetchone()

        assert reservation is not None
        assert reservation["customer_id"] == customer["id"]
        assert reservation["source_id"] == 1
        assert reservation["status"] == "PENDING"

        created_reservation_cleanup["reservation_ids"].append(
            reservation["id"]
        )
        created_reservation_cleanup["customer_ids"].append(
            customer["id"]
        )

    finally:
        connection.close()

def test_ui_displays_created_reservation_id(api_client):
    response = api_client.get(
        "/ui?reservation_created=1234"
    )

    assert response.status_code == 200
    assert "Rezerwacja #1234" in response.text

def test_get_reservation_returns_404_for_nonexistent_reservation(
    api_client,
):
    response = api_client.get(
        "/api/reservations/999999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"

def test_get_reservation_ui_returns_200(
    api_client,
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 7, 10),
        check_out=date(2031, 7, 17),
        guests_count=2,
    )

    db_connection.commit()

    reservation = reservation_repository.get_by_id(
        reservation_id
    )



    response = api_client.get(
        f"/ui/reservations/{reservation_id}"
    )


    assert response.status_code == 200
    assert f"Rezerwacja #{reservation_id}" in response.text
    assert "Domek 1" in response.text
    assert "2031-07-10" in response.text
    assert "2031-07-17" in response.text
    assert "2" in response.text


def test_get_reservation_ui_returns_404_for_nonexistent_reservation(
    api_client,
):
    
    response = api_client.get(
        "/ui/reservations/999999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"

