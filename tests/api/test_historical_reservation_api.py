from datetime import date
from decimal import Decimal

from app.repositories.reservation_repository import ReservationRepository


def test_create_historical_reservation(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    response = api_client.post(
        "/ui/reservations/historical",
        data={
            "cottage_id": "1",
            "source_id": "4",
            "check_in": "2026-07-10",
            "check_out": "2026-07-17",
            "guests_count": "2",
            "total_amount": "2100.00",
            "accounting_included": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    location = response.headers["location"]

    reservation_id = int(
        location.split("/")[-1]
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    assert reservation_id > 0

def test_create_historical_reservation_includes_accounting(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    response = api_client.post(
        "/ui/reservations/historical",
        data={
            "cottage_id": "1",
            "source_id": "2",  # BOOKING
            "check_in": "2026-07-20",
            "check_out": "2026-07-27",
            "guests_count": "4",
            "total_amount": "2500.00",
            "accounting_included": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    reservation_id = int(
        response.headers["location"].split("/")[-1]
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

