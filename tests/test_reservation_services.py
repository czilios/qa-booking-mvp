from datetime import date
import pytest
from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import update_reservation


def test_update_reservation_changes_reservation(db_connection):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 8, 10),
        check_out=date(2027, 8, 17),
        guests_count=2,
    )

    update_reservation(
        connection=db_connection,
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

def test_update_reservation_rejects_conflicting_cottage(
    db_connection,
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

    with pytest.raises(ValueError, match="Cottage is not available"):
        update_reservation(
            connection=db_connection,
            reservation_id=reservation_id,
            cottage_id=2,
            source_id=1,
            check_in=date(2027, 8, 22),
            check_out=date(2027, 8, 25),
            guests_count=2,
        )