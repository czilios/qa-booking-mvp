from datetime import date
from decimal import Decimal

from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import create_historical_reservation


def test_create_historical_reservation_creates_confirmed_reservation(
    db_connection,
    created_reservation_cleanup,
):
    reservation_id = create_historical_reservation(
        connection=db_connection,
        cottage_id=1,
        source_id=4,
        check_in=date(2026, 7, 10),
        check_out=date(2026, 7, 17),
        guests_count=2,
        total_amount=Decimal("2100.00"),
        notes="testing",
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    repository = ReservationRepository(db_connection)

    reservation = repository.get_by_id(reservation_id)

    assert reservation["status"] == "CONFIRMED"
    assert reservation["source_id"] == 4
    assert reservation["accounting_included"] == 0
    assert Decimal(str(reservation["total_amount"])) == Decimal("2100.00")
    assert reservation["notes"] == "testing"


def test_create_historical_reservation_with_accounting_included(
    db_connection,
    created_reservation_cleanup,
):
    reservation_id = create_historical_reservation(
        connection=db_connection,
        cottage_id=1,
        source_id=2,
        check_in=date(2026, 7, 20),
        check_out=date(2026, 7, 27),
        guests_count=4,
        total_amount=Decimal("2500.00"),
        notes="testing",
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    repository = ReservationRepository(db_connection)

    reservation = repository.get_by_id(reservation_id)

    assert reservation["status"] == "CONFIRMED"
    assert reservation["source_id"] == 2
    assert reservation["accounting_included"] == 1
    assert Decimal(
        str(reservation["total_amount"])
    ) == Decimal("2500.00")