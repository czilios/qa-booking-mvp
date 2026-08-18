from datetime import date

from app.repositories.reservation_repository import ReservationRepository

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

