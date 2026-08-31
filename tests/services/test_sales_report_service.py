from datetime import date, datetime
from decimal import Decimal

from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository
from app.sales_report_service import generate_sales_report


def test_sales_report_uses_check_in_month(
    db_connection,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
    )

    report = generate_sales_report(
        db_connection,
        start_date=date(2027, 10, 1),
        end_date=date(2027, 11, 1),
    )

    reservation_ids = {
        reservation["id"]
        for reservation in report["reservations"]
    }

    assert reservation_id in reservation_ids
def test_sales_report_assigns_cross_month_stay_to_check_in_month(
    db_connection,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 9, 29),
        check_out=date(2027, 10, 13),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("3000.00"),
    )


    september_report = generate_sales_report(
        db_connection,
        start_date=date(2027, 9, 1),
        end_date=date(2027, 10, 1),
    )

    october_report = generate_sales_report(
        db_connection,
        start_date=date(2027, 10, 1),
        end_date=date(2027, 11, 1),
    )

    september_ids = {
        reservation["id"]
        for reservation in september_report["reservations"]
    }

    october_ids = {
        reservation["id"]
        for reservation in october_report["reservations"]
    }

    assert reservation_id in september_ids
    assert reservation_id not in october_ids

def test_sales_report_excludes_cancelled_reservation(
    db_connection,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CANCELLED",
        total_amount=Decimal("1960.00"),
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2027, 10, 1),
        end_date=date(2027, 11, 1),
    )

    reservation_ids = {
        reservation["id"]
        for reservation in report["reservations"]
    }

    assert reservation_id not in reservation_ids

def test_sales_report_uses_check_in_month_regardless_of_payment_date(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2027, 7, 28),
        check_out=date(2027, 8, 4),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("2100.00"),
        status="UNPAID",
    )

    payment_repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=datetime(2027, 8, 6, 12, 0, 0),
    )

    july_report = generate_sales_report(
        db_connection,
        start_date=date(2027, 7, 1),
        end_date=date(2027, 8, 1),
    )

    august_report = generate_sales_report(
        db_connection,
        start_date=date(2027, 8, 1),
        end_date=date(2027, 9, 1),
    )

    july_ids = {
        reservation["id"]
        for reservation in july_report["reservations"]
    }

    august_ids = {
        reservation["id"]
        for reservation in august_report["reservations"]
    }

    assert reservation_id in july_ids
    assert reservation_id not in august_ids

def test_sales_report_resolves_booking_source(
    db_connection,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2027, 10, 1),
        end_date=date(2027, 11, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["source_code"] == "BOOKING"
    assert reservation["source_name"] == "Booking.com"

def test_sales_report_sums_total_amount(
    db_connection,created_reservation_cleanup
    ):
    repository = ReservationRepository(db_connection)

    first_reservation_id = repository.create(
    cottage_id=1,
    source_id=1,
    check_in=date(2028, 10, 10),
    check_out=date(2028, 10, 12),
    guests_count=2,
    status="CONFIRMED",
    total_amount=Decimal("1000.00"),
    )

    second_reservation_id = repository.create(
    cottage_id=2,
    source_id=2,
    check_in=date(2028, 10, 15),
    check_out=date(2028, 10, 18),
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


    report = generate_sales_report(
        db_connection,
        start_date=date(2028, 10, 1),
        end_date=date(2028, 11, 1),
    )

    assert report["total_amount"] == Decimal("2500.00")

def test_sales_report_handles_null_total_amount(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2028, 12, 10),
        check_out=date(2028, 12, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=None,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2028, 12, 1),
        end_date=date(2029, 1, 1),
    )

    assert report["total_amount"] == Decimal("0.00")

def test_sales_report_summarizes_sales_by_source(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    direct_reservation_id = repository.create(
        cottage_id=1,
        source_id=1,  # DIRECT
        check_in=date(2028, 11, 5),
        check_out=date(2028, 11, 8),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    booking_reservation_id = repository.create(
        cottage_id=2,
        source_id=2,  # BOOKING
        check_in=date(2028, 11, 10),
        check_out=date(2028, 11, 15),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1500.00"),
    )

    belvilla_reservation_id = repository.create(
        cottage_id=3,
        source_id=4,  # BELVILLA
        check_in=date(2028, 11, 20),
        check_out=date(2028, 11, 25),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2000.00"),
    )

    created_reservation_cleanup["reservation_ids"].extend(
        [
            direct_reservation_id,
            booking_reservation_id,
            belvilla_reservation_id,
        ]
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2028, 11, 1),
        end_date=date(2028, 12, 1),
    )

    assert report["by_source"][1] == Decimal("1000.00")
    assert report["by_source"][2] == Decimal("1500.00")
    assert report["by_source"][4] == Decimal("2000.00")

def test_sales_report_sums_multiple_reservations_from_same_source(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    first_reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2028, 12, 5),
        check_out=date(2028, 12, 8),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    second_reservation_id = repository.create(
        cottage_id=2,
        source_id=2,  # BOOKING
        check_in=date(2028, 12, 10),
        check_out=date(2028, 12, 14),
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


    report = generate_sales_report(
        db_connection,
        start_date=date(2028, 12, 1),
        end_date=date(2029, 1, 1),
    )

    assert report["by_source"][2] == Decimal("2500.00")

def test_sales_report_source_totals_equal_overall_total(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_data = [
        (1, 1000),
        (2, 1500),
        (2, 1000),
        (4, 2000),
    ]

    reservation_ids = []

    for source_id, amount in reservation_data:
        reservation_id = repository.create(
            cottage_id=1,
            source_id=source_id,
            check_in=date(2029, 10, 10),
            check_out=date(2029, 10, 12),
            guests_count=2,
            status="CONFIRMED",
            total_amount=Decimal(str(amount)),
        )
        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2029, 10, 1),
        end_date=date(2029, 11, 1),
    )

    source_total = sum(
        report["by_source"].values(),
        Decimal("0.00"),
    )

    assert source_total == report["total_amount"]
    assert report["total_amount"] == Decimal("5500.00")

def test_sales_report_excludes_pending_and_expired_reservations(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_ids = []

    for status in ("PENDING", "EXPIRED"):
        reservation_id = repository.create(
            cottage_id=1,
            source_id=1,
            check_in=date(2029, 11, 10),
            check_out=date(2029, 11, 15),
            guests_count=2,
            status=status,
            total_amount=Decimal("2000.00"),
        )

        reservation_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(
        reservation_ids
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2029, 11, 1),
        end_date=date(2029, 12, 1),
    )

    reservation_ids_in_report = {
        reservation["id"]
        for reservation in report["reservations"]
    }

    assert reservation_ids_in_report.isdisjoint(reservation_ids)
    assert report["total_amount"] == Decimal("0.00")

def test_sales_report_includes_customer_phone(
    db_connection,
    created_reservation_cleanup,
):
    customer_phone = "+48500100200"

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO customers (
                phone
            )
            VALUES (%s)
            """,
            (customer_phone,),
        )

        customer_id = cursor.lastrowid

    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,
        customer_id=customer_id,
        check_in=date(2030, 10, 10),
        check_out=date(2030, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2100.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    report = generate_sales_report(
        db_connection,
        start_date=date(2030, 10, 1),
        end_date=date(2030, 11, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["phone"] == customer_phone

def test_sales_report_calculates_paid_amount_and_balance(
    db_connection,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,  # DIRECT
        check_in=date(2030, 11, 10),
        check_out=date(2030, 11, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
        status="UNPAID",
    )

    payment_repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=datetime(2030, 11, 1, 12, 0, 0),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2030, 11, 1),
        end_date=date(2030, 12, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["paid_amount"] == Decimal("500.00")
    assert reservation["balance"] == Decimal("500.00")

def test_sales_report_calculates_fully_paid_reservation(
    db_connection,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2030, 12, 10),
        check_out=date(2030, 12, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1000.00"),
        status="UNPAID",
    )

    payment_repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=datetime(2030, 12, 1, 12, 0, 0),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2030, 12, 1),
        end_date=date(2031, 1, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["paid_amount"] == Decimal("1000.00")
    assert reservation["balance"] == Decimal("0.00")

def test_sales_report_sums_multiple_paid_payments_for_reservation(
    db_connection,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 1, 10),
        check_out=date(2031, 1, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1950.00"),
    )

    first_payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("900.00"),
        status="UNPAID",
    )

    second_payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1050.00"),
        status="UNPAID",
    )

    payment_repository.mark_payment_as_paid(
        payment_id=first_payment_id,
        paid_at=datetime(2031, 1, 2, 12, 0, 0),
    )

    payment_repository.mark_payment_as_paid(
        payment_id=second_payment_id,
        paid_at=datetime(2031, 1, 5, 12, 0, 0),
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2031, 1, 1),
        end_date=date(2031, 2, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["paid_amount"] == Decimal("1950.00")
    assert reservation["balance"] == Decimal("0.00")

def test_sales_report_excludes_refunded_amount_from_paid_amount(
    db_connection,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 2, 10),
        check_out=date(2031, 2, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    paid_payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("1000.00"),
        status="UNPAID",
    )

    payment_repository.mark_payment_as_paid(
        payment_id=paid_payment_id,
        paid_at=datetime(2031, 2, 1, 12, 0, 0),
    )

    refunded_payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("400.00"),
        status="REFUNDED",
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2031, 2, 1),
        end_date=date(2031, 3, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["paid_amount"] == Decimal("600.00")
    assert reservation["balance"] == Decimal("400.00")

def test_sales_report_treats_forfeited_payment_as_paid(
    db_connection,
    created_reservation_cleanup,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2031, 3, 10),
        check_out=date(2031, 3, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("1000.00"),
        status="FORFEITED",
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )


    report = generate_sales_report(
        db_connection,
        start_date=date(2031, 3, 1),
        end_date=date(2031, 4, 1),
    )

    reservation = next(
        reservation
        for reservation in report["reservations"]
        if reservation["id"] == reservation_id
    )

    assert reservation["paid_amount"] == Decimal("1000.00")
    assert reservation["balance"] == Decimal("0.00")
