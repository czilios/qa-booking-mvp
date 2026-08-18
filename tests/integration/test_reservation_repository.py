from datetime import date, datetime
import pytest

from app.repositories.reservation_repository import ReservationRepository


def test_reservation_repository_creates_reservation(db_connection):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 7),
        guests_count=2,
        status="PENDING",
        expires_at=datetime(2026, 8, 17, 20, 0, 0),
    )

    reservation = repository.get_by_id(reservation_id)

    assert reservation["id"] == reservation_id
    assert reservation["cottage_id"] == 1
    assert reservation["source_id"] == 1
    assert reservation["check_in"] == date(2026, 11, 1)
    assert reservation["check_out"] == date(2026, 11, 7)
    assert reservation["guests_count"] == 2
    assert reservation["status"] == "PENDING"

def test_get_reservation_by_id_for_update(db_connection):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 11, 10),
        check_out=date(2026, 11, 15),
        guests_count=2,
        status="PENDING",
        expires_at=datetime(2026, 8, 17, 20, 0, 0),
    )

    reservation = repository.get_by_id_for_update(reservation_id)

    assert reservation is not None
    assert reservation["id"] == reservation_id
    assert reservation["cottage_id"] == 1
    assert reservation["status"] == "PENDING"

def test_get_active_reservations(db_connection):
    repository = ReservationRepository(db_connection)

    pending_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 7, 10),
        check_out=date(2027, 7, 17),
        guests_count=2,
        status="PENDING",
    )

    confirmed_id = repository.create(
        cottage_id=2,
        source_id=1,
        check_in=date(2027, 7, 10),
        check_out=date(2027, 7, 17),
        guests_count=2,
        status="CONFIRMED",
    )

    cancelled_id = repository.create(
        cottage_id=3,
        source_id=1,
        check_in=date(2027, 7, 10),
        check_out=date(2027, 7, 17),
        guests_count=2,
        status="CANCELLED",
    )

    reservations = repository.get_active_reservations()

    reservation_ids = {
        reservation["id"]
        for reservation in reservations
    }

    assert pending_id in reservation_ids
    assert confirmed_id in reservation_ids
    assert cancelled_id not in reservation_ids

def test_update_reservation(db_connection):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    repository.update(
        reservation_id=reservation_id,
        cottage_id=2,
        source_id=1,
        check_in=date(2027, 8, 20),
        check_out=date(2027, 8, 27),
        guests_count=3,
    )

    reservation = repository.get_by_id(reservation_id)

    assert reservation["cottage_id"] == 2
    assert reservation["check_in"] == date(2027, 8, 20)
    assert reservation["check_out"] == date(2027, 8, 27)
    assert reservation["guests_count"] == 3
def test_update_nonexistent_reservation_raises_error(db_connection):
    repository = ReservationRepository(db_connection)

    with pytest.raises(ValueError, match="Reservation not found"):
        repository.update(
            reservation_id=999999,
            cottage_id=1,
            source_id=1,
            check_in=date(2027, 8, 20),
            check_out=date(2027, 8, 27),
            guests_count=2,
        )