from datetime import date
from decimal import Decimal

from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.reservation_repository import ReservationRepository


def test_overall_report_includes_reservation(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        is_test_data=False,
        cottage_id=1,
        source_id=4,  # BELVILLA
        check_in=date(2044, 10, 10),
        check_out=date(2044, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )



    response = api_client.get(
        "/api/overall-report",
        params={
            "start_date": "2044-10-01",
            "end_date": "2044-11-01",
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
            is_test_data=False,
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
        is_test_data=False,
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


def test_overall_report_includes_bank_transaction_by_transaction_date(
    db_connection,
    api_client,
    created_reservation_cleanup,
    created_bank_transaction_cleanup,
):
    report_params = {
        "start_date": "2026-07-01",
        "end_date": "2026-08-01",
    }
    baseline_response = api_client.get(
        "/api/overall-report",
        params=report_params,
    )
    assert baseline_response.status_code == 200

    invoice_number = "TEST-CASHFLOW-JUL-2026"
    reservation_id = ReservationRepository(db_connection).create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1700.00"),
        invoice_number=invoice_number,
    )
    created_reservation_cleanup["reservation_ids"].append(reservation_id)

    transaction_id = BankTransactionRepository(db_connection).create(
        transaction_date=date(2026, 7, 7),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1700.00"),
        notes=invoice_number,
    )
    created_bank_transaction_cleanup.append(transaction_id)
    db_connection.commit()

    response = api_client.get(
        "/api/overall-report",
        params=report_params,
    )

    assert response.status_code == 200
    reported_increase = (
        Decimal(str(response.json()["total_amount"]))
        - Decimal(str(baseline_response.json()["total_amount"]))
    )
    assert reported_increase == Decimal("1700.00")
