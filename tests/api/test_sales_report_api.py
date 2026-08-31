from datetime import date
from decimal import Decimal

from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def test_sales_report_api_returns_report(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 10, 10),
        check_out=date(2031, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["reservations"]) == 1
    assert body["reservations"][0]["id"] == reservation_id
    assert Decimal(str(body["total_amount"])) == Decimal("1000.00")
def test_sales_report_api_rejects_invalid_date_range(
    api_client,
):
    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-11-01",
            "end_date": "2031-10-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "end_date must be after start_date"

def test_sales_report_api_includes_all_sources(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_ids = []

    for source_id in [1, 2, 4]:
        reservation_id = repository.create(
            cottage_id=1,
            source_id=source_id,
            check_in=date(2031, 10, 10),
            check_out=date(2031, 10, 12),
            guests_count=2,
            status="CONFIRMED",
            total_amount=Decimal("1000.00"),
        )

        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    returned_source_ids = {
        reservation["source_id"]
        for reservation in body["reservations"]
    }

    assert returned_source_ids == {1, 2, 4}
def test_sales_report_api_returns_total_amount(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_ids = []

    for amount in [
        Decimal("1000.00"),
        Decimal("1500.00"),
    ]:
        reservation_id = repository.create(
            cottage_id=1,
            source_id=1,
            check_in=date(2031, 10, 10),
            check_out=date(2031, 10, 12),
            guests_count=2,
            status="CONFIRMED",
            total_amount=amount,
        )

        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert Decimal(
        str(body["total_amount"])
    ) == Decimal("2500.00")

def test_sales_report_api_returns_sales_by_source(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    first_reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 10, 10),
        check_out=date(2031, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    second_reservation_id = repository.create(
        cottage_id=2,
        source_id=2,
        check_in=date(2031, 10, 15),
        check_out=date(2031, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1500.00"),
    )

    created_reservation_cleanup["reservation_ids"].extend(
        [
            first_reservation_id,
            second_reservation_id,
        ]
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert Decimal(
        str(body["by_source"]["1"])
    ) == Decimal("1000.00")

    assert Decimal(
        str(body["by_source"]["2"])
    ) == Decimal("1500.00")

def test_sales_report_api_returns_paid_amount_and_balance(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 10, 10),
        check_out=date(2031, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    payment_repository = PaymentRepository(db_connection)

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
        status="PAID",
        due_at=None,
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    reservation = next(
        reservation
        for reservation in body["reservations"]
        if reservation["id"] == reservation_id
    )

    assert Decimal(
        str(reservation["paid_amount"])
    ) == Decimal("500.00")

    assert Decimal(
        str(reservation["balance"])
    ) == Decimal("500.00")

def test_sales_report_api_excludes_cancelled_reservation(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 10, 10),
        check_out=date(2031, 10, 12),
        guests_count=2,
        status="CANCELLED",
        total_amount=Decimal("1000.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    returned_ids = {
        reservation["id"]
        for reservation in body["reservations"]
    }

    assert reservation_id not in returned_ids

def test_sales_report_api_excludes_reservation_outside_date_range(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 11, 5),
        check_out=date(2031, 11, 7),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    response = api_client.get(
        "/api/sales-report",
        params={
            "start_date": "2031-10-01",
            "end_date": "2031-11-01",
        },
    )

    assert response.status_code == 200

    body = response.json()

    returned_ids = {
        reservation["id"]
        for reservation in body["reservations"]
    }

    assert reservation_id not in returned_ids