from datetime import date

from app.repositories.reservation_repository import ReservationRepository


def test_update_reservation_returns_200(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    response = api_client.put(
        f"/api/reservations/{reservation_id}",
        json={
            "cottage_id": 2,
            "source_id": 1,
            "check_in": "2027-08-20",
            "check_out": "2027-08-27",
            "guests_count": 3,
        },
    )

    assert response.status_code == 200
def test_update_reservation_rejects_conflicting_cottage(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    repository.create(
        cottage_id=2,
        source_id=1,
        check_in=date(2027, 8, 20),
        check_out=date(2027, 8, 27),
        guests_count=2,
    )

    response = api_client.put(
        f"/api/reservations/{reservation_id}",
        json={
            "cottage_id": 2,
            "source_id": 1,
            "check_in": "2027-08-22",
            "check_out": "2027-08-25",
            "guests_count": 2,
        },
    )

    assert response.status_code == 409
def test_update_reservation_returns_404_for_nonexistent_reservation(
    api_client,
):
    response = api_client.put(
        "/api/reservations/999999",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-20",
            "check_out": "2027-08-27",
            "guests_count": 2,
        },
    )

    assert response.status_code == 404

def test_update_reservation_rejects_negative_guests(
    api_client,
):
    response = api_client.put(
        "/api/reservations/1",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-20",
            "check_out": "2027-08-27",
            "guests_count": -1,
        },
    )

    assert response.status_code == 422
def test_update_reservation_rejects_too_many_guests(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    response = api_client.put(
        f"/api/reservations/{reservation_id}",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-20",
            "check_out": "2027-08-27",
            "guests_count": 5,
        },
    )

    assert response.status_code == 409
def test_update_reservation_rejects_invalid_dates(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    response = api_client.put(
        f"/api/reservations/{reservation_id}",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-20",
            "check_out": "2027-08-15",
            "guests_count": 2,
        },
    )

    assert response.status_code == 400
def test_update_reservation_keeps_same_cottage_and_dates(
    db_connection,
    api_client,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    response = api_client.put(
        f"/api/reservations/{reservation_id}",
        json={
            "cottage_id": 1,
            "source_id": 1,
            "check_in": "2027-08-10",
            "check_out": "2027-08-17",
            "guests_count": 3,
        },
    )

    assert response.status_code == 200