from datetime import date, datetime
from decimal import Decimal

from app.repositories.customer_repository import CustomerRepository
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def set_reservation_created_at(db_connection, reservation_id, created_at):
    with db_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE reservations SET created_at = %s WHERE id = %s",
            (created_at, reservation_id),
        )


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
        is_test_data=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )
    set_reservation_created_at(
        db_connection,
        reservation_id,
        date(2031, 10, 10),
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
        is_test_data=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )
    set_reservation_created_at(
        db_connection,
        reservation_id,
        date(2031, 10, 10),
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
            is_test_data=False,
        )

        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids
    )
    for reservation_id in reservation_ids:
        set_reservation_created_at(
            db_connection,
            reservation_id,
            date(2031, 10, 10),
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


def test_sales_report_ui_shows_reservation_details_and_optional_phone(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    customer_id = CustomerRepository(db_connection).create(
        first_name="Alicja",
        last_name="Raport",
        phone="+48500100203",
    )
    created_reservation_cleanup["customer_ids"].append(customer_id)
    repository = ReservationRepository(db_connection)
    reservations = [
        {
            "name": "direct_with_phone",
            "cottage_id": 1,
            "source_id": 1,
            "customer_id": customer_id,
            "check_in": date(2033, 11, 10),
            "check_out": date(2033, 11, 13),
            "amount": Decimal("3210.00"),
            "created_at": datetime(2033, 10, 2, 14, 30),
        },
        {
            "name": "booking_without_phone",
            "cottage_id": 2,
            "source_id": 2,
            "customer_id": None,
            "check_in": date(2033, 11, 20),
            "check_out": date(2033, 11, 25),
            "amount": Decimal("4250.00"),
            "created_at": datetime(2033, 10, 3, 9, 0),
        },
        {
            "name": "belvilla_without_phone",
            "cottage_id": 3,
            "source_id": 4,
            "customer_id": None,
            "check_in": date(2033, 12, 2),
            "check_out": date(2033, 12, 5),
            "amount": Decimal("1800.00"),
            "created_at": datetime(2033, 10, 4, 10, 0),
        },
        {
            "name": "created_outside_selected_month",
            "cottage_id": 4,
            "source_id": 1,
            "customer_id": None,
            "check_in": date(2033, 10, 30),
            "check_out": date(2033, 11, 2),
            "amount": Decimal("900.00"),
            "created_at": datetime(2033, 11, 1, 10, 0),
        },
    ]
    reservation_ids = {}

    for reservation in reservations:
        reservation_id = repository.create(
            cottage_id=reservation["cottage_id"],
            source_id=reservation["source_id"],
            customer_id=reservation["customer_id"],
            check_in=reservation["check_in"],
            check_out=reservation["check_out"],
            guests_count=2,
            status="CONFIRMED",
            total_amount=reservation["amount"],
            is_test_data=False,
        )
        set_reservation_created_at(
            db_connection,
            reservation_id,
            reservation["created_at"],
        )
        reservation_ids[reservation["name"]] = reservation_id

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids.values()
    )
    response = api_client.get(
        "/ui/reports/sales",
        params={"month": 10, "year": 2033},
    )

    assert response.status_code == 200
    assert 'name="month"' in response.text
    assert 'name="year"' in response.text
    assert str(reservation_ids["direct_with_phone"]) in response.text
    assert str(reservation_ids["booking_without_phone"]) in response.text
    assert str(reservation_ids["belvilla_without_phone"]) in response.text
    assert str(reservation_ids["created_outside_selected_month"]) not in response.text
    assert "+48500100203" in response.text
    assert "Direct" in response.text
    assert "Booking" in response.text
    assert "Belvilla" in response.text
    assert "CONFIRMED" in response.text
    assert "2033-10-02" in response.text
    assert "2033-11-10" in response.text
    assert "2033-11-13" in response.text
    assert "3 210,00 zł" in response.text
    assert "4 250,00 zł" in response.text

    booking_row = response.text.split(
        f'<tr data-reservation-id="{reservation_ids["booking_without_phone"]}">',
        1,
    )[1].split("</tr>", 1)[0]
    assert "—" in booking_row


def test_sales_report_ui_displays_full_year_by_reservation_creation_date(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)
    reservation_ids = []

    for month, created_at in [
        (1, datetime(2034, 1, 5, 12, 0)),
        (12, datetime(2034, 12, 15, 12, 0)),
        (1, datetime(2035, 1, 5, 12, 0)),
    ]:
        reservation_id = repository.create(
            cottage_id=month % 6 + 1,
            source_id=1,
            check_in=date(2035, month, 10),
            check_out=date(2035, month, 12),
            guests_count=2,
            status="CONFIRMED",
            total_amount=Decimal("1000.00"),
            is_test_data=False,
        )
        set_reservation_created_at(db_connection, reservation_id, created_at)
        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(reservation_ids)
    response = api_client.get(
        "/ui/reports/sales",
        params={"month": 0, "year": 2034},
    )

    assert response.status_code == 200
    assert 'value="0" selected' in response.text
    assert 'value="2034" selected' in response.text
    assert str(reservation_ids[0]) in response.text
    assert str(reservation_ids[1]) in response.text
    assert str(reservation_ids[2]) not in response.text

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
        is_test_data=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )
    set_reservation_created_at(
        db_connection,
        reservation_id,
        date(2031, 10, 10),
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

def test_reservation_stores_invoice_number(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2032, 10, 10),
        check_out=date(2032, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        invoice_number="FV/2032/001",
        is_test_data=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    reservation = repository.get_by_id(reservation_id)

    assert reservation["invoice_number"] == "FV/2032/001"

def test_sales_report_ui_displays_invoice_number(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2032, 10, 10),
        check_out=date(2032, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        invoice_number="FV/2032/001",
        is_test_data=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    set_reservation_created_at(
        db_connection,
        reservation_id,
        datetime(2032, 10, 5, 12, 0),
    )

    response = api_client.get(
        "/ui/reports/sales",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200
    assert "FV/2032/001" in response.text


