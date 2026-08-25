from datetime import date
from decimal import Decimal

from app.repositories.reservation_repository import ReservationRepository


def test_overall_report_includes_reservation(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=4,  # BELVILLA
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    response = api_client.get(
        "/api/overall-report",
        params={
            "start_date": "2027-10-01",
            "end_date": "2027-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["reservations"]) == 1

    reservation = body["reservations"][0]

    assert reservation["id"] == reservation_id
    assert reservation["source_id"] == 4
    assert Decimal(
        str(reservation["total_amount"])
    ) == Decimal("2100.00")

def test_overall_report_includes_all_sources(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_ids = []

    for source_id in [1, 2, 4]:
        reservation_id = reservation_repository.create(
            cottage_id=1,
            source_id=source_id,
            check_in=date(2027, 10, 10),
            check_out=date(2027, 10, 17),
            guests_count=2,
            status="CONFIRMED",
            total_amount=Decimal("2100.00"),
        )

        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids
    )

    db_connection.commit()

    response = api_client.get(
        "/api/overall-report",
        params={
            "start_date": "2027-10-01",
            "end_date": "2027-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["reservations"]) == 3

    returned_source_ids = {
        reservation["source_id"]
        for reservation in body["reservations"]
    }

    assert returned_source_ids == {1, 2, 4}

def test_overall_report_includes_non_accounting_reservation(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=4,  # BELVILLA
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
        accounting_included=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    response = api_client.get(
        "/api/overall-report",
        params={
            "start_date": "2027-10-01",
            "end_date": "2027-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    reservation_ids = {
        reservation["id"]
        for reservation in body["reservations"]
    }

    assert reservation_id in reservation_ids

