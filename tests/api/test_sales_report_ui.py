from datetime import date
from decimal import Decimal

from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def test_sales_report_ui_returns_200(
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
        "/ui/reports/sales",
        params={
            "month": 10,
            "year": 2031,
        },
    )

    assert response.status_code == 200

def test_sales_report_ui_displays_reservation(
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
        "/ui/reports/sales",
        params={
            "month": 10,
            "year": 2031,
        },
    )

    assert response.status_code == 200

    assert str(reservation_id) in response.text
    assert "1" in response.text
    assert "2031-10-10" in response.text
    assert "2031-10-12" in response.text
    assert "1 000,00 zł" in response.text

def test_sales_report_ui_displays_sales_by_source(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_ids = []

    for source_id, amount in [
        (1, Decimal("1000.00")),
        (2, Decimal("1500.00")),
        (4, Decimal("500.00")),
    ]:
        reservation_id = repository.create(
            cottage_id=1,
            source_id=source_id,
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
        "/ui/reports/sales",
        params={
            "month": 10,
            "year": 2031,
        },
    )

    assert response.status_code == 200

    assert "1 000,00 zł" in response.text
    assert "1 500,00 zł" in response.text
    assert "500,00 zł" in response.text

def test_sales_report_ui_displays_paid_amount_and_balance(
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

    payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
        status="PAID",
    )

    response = api_client.get(
        "/ui/reports/sales",
        params={
            "month": 10,
            "year": 2031,
        },
    )

    assert response.status_code == 200

    assert "500,00 zł" in response.text

def test_sales_report_ui_displays_empty_report(
    db_connection,
    api_client,
):
    response = api_client.get(
        "/ui/reports/sales",
        params={
            "month": 11,
            "year": 2035,
        },
    )

    assert response.status_code == 200
    assert "Brak rezerwacji" in response.text