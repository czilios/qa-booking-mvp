from datetime import date
from decimal import Decimal

import pytest

from app.repositories.reservation_repository import ReservationRepository


def test_accounting_report_includes_completed_booking_reservations(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    response = api_client.get(
        "/api/accounting-report",
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
    assert Decimal(
        str(reservation["total_amount"])
    ) == Decimal("2100.00")


@pytest.mark.parametrize(
    "check_out, expected_count",
    [
        (date(2027, 9, 30), 0),
        (date(2027, 10, 1), 1),
        (date(2027, 11, 1), 0),
    ],
)
def test_accounting_report_respects_date_boundaries(
    db_connection,
    api_client,
    created_reservation_cleanup,
    check_out,
    expected_count,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=2,
        check_in=date(2027, 9, 25),
        check_out=check_out,
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    response = api_client.get(
        "/api/accounting-report",
        params={
            "start_date": "2027-10-01",
            "end_date": "2027-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["reservations"]) == expected_count

def test_accounting_report_respects_accounting_included(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    included_reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
        accounting_included=True,
    )

    excluded_reservation_id = reservation_repository.create(
        cottage_id=2,
        source_id=1,  # DIRECT
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1800.00"),
        accounting_included=False,
    )

    created_reservation_cleanup["reservation_ids"].extend(
        [
            included_reservation_id,
            excluded_reservation_id,
        ]
    )

    db_connection.commit()

    response = api_client.get(
        "/api/accounting-report",
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

    assert included_reservation_id in reservation_ids
    assert excluded_reservation_id not in reservation_ids

def test_accounting_report_excludes_non_accounting_reservation(
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
        "/api/accounting-report",
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

    assert reservation_id not in reservation_ids

def test_accounting_report_ui_get(
    api_client,
):
    response = api_client.get(
        "/ui/reports/accounting?year=2026"
    )

    assert response.status_code == 200
    assert "Raport księgowy" in response.text
    assert "Czerwiec" in response.text
    assert "Lipiec" in response.text
    assert "Sierpień" in response.text