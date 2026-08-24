from datetime import date
from urllib import response

from app.repositories import reservation_repository
from app.repositories.reservation_repository import ReservationRepository
from tests.api.conftest import api_client

def test_cancel_reservation_returns_204(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 9, 10),
        check_out=date(2027, 9, 17),
        guests_count=2,
    )

    response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert response.status_code == 204

    reservation = repository.get_by_id_for_update(
        reservation_id
    )

    assert reservation["status"] == "CANCELLED"

def test_cancel_reservation_returns_404_for_nonexistent_reservation(
    api_client,
):
    response = api_client.delete(
        "/api/reservations/999999"
    )

    assert response.status_code == 404
def test_cancelled_reservation_does_not_block_cottage(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 9, 10),
        check_out=date(2027, 9, 17),
        guests_count=2,
    )

    response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert response.status_code == 204

    availability_response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-09-10",
            "check_out": "2027-09-17",
        },
    )

    assert availability_response.status_code == 200

    available_cottages = availability_response.json()["cottages"]

    assert 1 in available_cottages

def test_cancel_already_cancelled_reservation_returns_409(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 9, 10),
        check_out=date(2027, 9, 17),
        guests_count=2,
    )

    first_response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert first_response.status_code == 204

    second_response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert second_response.status_code == 409

def test_cancel_reservation_returns_204(
    api_client,
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2032, 7, 10),
        check_out=date(2032, 7, 17),
        guests_count=2,
    )

    db_connection.commit()

    response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert response.status_code == 204

    reservation = reservation_repository.get_by_id(
        reservation_id
    )

    assert reservation["status"] == "CANCELLED"

def test_cancelled_reservation_makes_cottage_available(
    api_client,
    db_connection,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2092, 8, 10),
        check_out=date(2092, 8, 17),
        guests_count=2,
    )

    created_reservation_cleanup["reservation_ids"].append(
    reservation_id
    )

    db_connection.commit()

    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2092-08-10",
            "check_out": "2092-08-17",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert 1 not in body["cottages"]
    response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert response.status_code == 204

    reservation = reservation_repository.get_by_id(
        reservation_id
    )

    active_reservations = (
        reservation_repository.get_active_reservations()
    )

    assert reservation not in active_reservations
    

    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2092-08-10",
            "check_out": "2092-08-17",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert 1 in body["cottages"]

def test_cancel_nonexistent_reservation_returns_404(
    api_client,
):
    response = api_client.delete(
        "/api/reservations/999999999"
    )

    assert response.status_code == 404

def test_cancel_already_cancelled_reservation_returns_error(
    api_client,
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2033, 8, 10),
        check_out=date(2033, 8, 17),
        guests_count=2,
    )

    db_connection.commit()

    first_response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    assert first_response.status_code == 204

    second_response = api_client.delete(
        f"/api/reservations/{reservation_id}"
    )

    print(second_response.status_code, second_response.text)