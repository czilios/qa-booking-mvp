from datetime import datetime, date
from decimal import Decimal

import pytest
from app.payment_service import create_payment
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository
from app.payment_service import mark_payment_as_paid, generate_payment_report


def test_mark_payment_as_paid(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    paid_at = datetime(2027, 9, 1, 12, 0, 0)

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=payment_id,
        paid_at=paid_at,
    )

    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment["status"] == "PAID"
    assert payment["paid_at"] == paid_at

def test_mark_payment_as_paid_rejects_nonexistent_payment(
    db_connection,
):
    with pytest.raises(
        ValueError,
        match="Payment not found",
    ):
        mark_payment_as_paid(
            connection=db_connection,
            payment_id=999999,
            paid_at=datetime(2027, 9, 1, 12, 0, 0),
        )

def test_mark_payment_as_paid_rejects_already_paid_payment(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
        status="PAID",
    )

    with pytest.raises(
        ValueError,
        match="Payment is already PAID",
    ):
        mark_payment_as_paid(
            connection=db_connection,
            payment_id=payment_id,
            paid_at=datetime(2027, 9, 1, 12, 0, 0),
        )

def test_create_payment_rejects_zero_amount(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero",
    ):
        create_payment(
            connection=db_connection,
            reservation_id=reservation_id,
            payment_type="DEPOSIT",
            amount=Decimal("0.00"),
        )

def test_create_payment_rejects_nonexistent_reservation(
    db_connection,
):
    with pytest.raises(
        ValueError,
        match="Reservation not found",
    ):
        create_payment(
            connection=db_connection,
            reservation_id=999999,
            payment_type="DEPOSIT",
            amount=Decimal("500.00"),
        )

def test_create_payment_creates_payment(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    payment_id = create_payment(
        connection=db_connection,
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment["id"] == payment_id
    assert payment["reservation_id"] == reservation_id
    assert payment["type"] == "DEPOSIT"
    assert payment["amount"] == Decimal("500.00")
    assert payment["status"] == "UNPAID"
    assert payment["paid_at"] is None

def test_create_payment_stores_due_at(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    due_at = datetime(2027, 10, 1, 12, 0, 0)

    payment_id = create_payment(
        connection=db_connection,
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
        due_at=due_at,
    )

    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment["due_at"] == due_at

def test_create_payment_rejects_negative_amount(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    with pytest.raises(
        ValueError,
        match="Payment amount must be greater than zero",
    ):
        create_payment(
            connection=db_connection,
            reservation_id=reservation_id,
            payment_type="DEPOSIT",
            amount=Decimal("-500.00"),
        )

@pytest.mark.parametrize(
    "payment_type",
    ["DEPOSIT", "BALANCE"],
)
def test_create_payment_accepts_valid_payment_type(
    db_connection,
    payment_type,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    payment_id = create_payment(
        connection=db_connection,
        reservation_id=reservation_id,
        payment_type=payment_type,
        amount=Decimal("500.00"),
    )

    payment_repository = PaymentRepository(db_connection)
    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment["type"] == payment_type

def test_create_payment_rejects_invalid_payment_type(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    with pytest.raises(
        ValueError,
        match="Invalid payment type",
    ):
        create_payment(
            connection=db_connection,
            reservation_id=reservation_id,
            payment_type="WHATEVER",
            amount=Decimal("500.00"),
        )

def test_generate_payment_report_returns_payment_with_reservation_data(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 11, 10),
        check_out=date(2027, 11, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    paid_at = datetime(2027, 11, 1, 14, 30, 0)

    mark_payment_as_paid(
    connection=db_connection,
    payment_id=payment_id,
    paid_at=paid_at,
)

    report = generate_payment_report(
        connection=db_connection,
        start_date=date(2027, 11, 1),
        end_date=date(2027, 12, 1),
        vat_rate=8,
    )

    assert len(report) == 1

    row = report[0]

    assert row["payment_id"] == payment_id
    assert row["reservation_id"] == reservation_id
    assert row["payment_type"] == "DEPOSIT"
    assert row["paid_at"] == paid_at

    assert row["check_in"] == date(2027, 11, 10)
    assert row["check_out"] == date(2027, 11, 17)

    assert row["gross_amount"] == Decimal("500.00")
    assert row["net_amount"] == Decimal("462.96")
    assert row["vat_amount"] == Decimal("37.04")
    assert row["vat_rate"] == Decimal("8")

def test_generate_payment_report_returns_multiple_payments(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 11, 10),
        check_out=date(2027, 11, 17),
        guests_count=2,
    )

    payment_id_1 = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment_id_2 = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1200.00"),
    )

    paid_at = datetime(2027, 11, 1, 14, 30, 0)

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=payment_id_1,
        paid_at=paid_at,
    )

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=payment_id_2,
        paid_at=paid_at,
    )

    report = generate_payment_report(
        connection=db_connection,
        start_date=date(2027, 11, 1),
        end_date=date(2027, 12, 1),
        vat_rate=8,
    )

    assert len(report) == 2

    assert report[0]["payment_id"] == payment_id_1
    assert report[0]["gross_amount"] == Decimal("500.00")

    assert report[1]["payment_id"] == payment_id_2
    assert report[1]["gross_amount"] == Decimal("1200.00")


def test_generate_payment_report_calculates_zero_vat(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 12, 10),
        check_out=date(2027, 12, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    paid_at = datetime(2027, 12, 1, 14, 30, 0)

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=payment_id,
        paid_at=paid_at,
    )

    report = generate_payment_report(
        connection=db_connection,
        start_date=date(2027, 12, 1),
        end_date=date(2028, 1, 1),
        vat_rate=0,
    )

    assert len(report) == 1

    row = report[0]

    assert row["gross_amount"] == Decimal("500.00")
    assert row["net_amount"] == Decimal("500.00")
    assert row["vat_amount"] == Decimal("0.00")
    assert row["vat_rate"] == Decimal("0")


def test_generate_payment_report_calculates_23_percent_vat(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2028, 1, 10),
        check_out=date(2028, 1, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1230.00"),
    )

    paid_at = datetime(2028, 1, 1, 14, 30, 0)

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=payment_id,
        paid_at=paid_at,
    )

    report = generate_payment_report(
        connection=db_connection,
        start_date=date(2028, 1, 1),
        end_date=date(2028, 2, 1),
        vat_rate=23,
    )

    assert len(report) == 1

    row = report[0]

    assert row["gross_amount"] == Decimal("1230.00")
    assert row["net_amount"] == Decimal("1000.00")
    assert row["vat_amount"] == Decimal("230.00")
    assert row["vat_rate"] == Decimal("23")

def test_generate_payment_report_calculates_23_percent_vat(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2028, 1, 10),
        check_out=date(2028, 1, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1230.00"),
    )

    paid_at = datetime(2028, 1, 1, 14, 30, 0)

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=payment_id,
        paid_at=paid_at,
    )

    report = generate_payment_report(
        connection=db_connection,
        start_date=date(2028, 1, 1),
        end_date=date(2028, 2, 1),
        vat_rate=23,
    )

    assert len(report) == 1

    row = report[0]

    assert row["gross_amount"] == Decimal("1230.00")
    assert row["net_amount"] == Decimal("1000.00")
    assert row["vat_amount"] == Decimal("230.00")
    assert row["vat_rate"] == Decimal("23")

def test_generate_payment_report_filters_by_source(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    belvilla_reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=4,
        check_in=date(2028, 2, 10),
        check_out=date(2028, 2, 17),
        guests_count=2,
    )

    booking_reservation_id = reservation_repository.create(
        cottage_id=2,
        source_id=1,
        check_in=date(2028, 2, 10),
        check_out=date(2028, 2, 17),
        guests_count=2,
    )

    belvilla_payment_id = payment_repository.create_payment(
        reservation_id=belvilla_reservation_id,
        payment_type="BALANCE",
        amount=Decimal("900.00"),
    )

    booking_payment_id = payment_repository.create_payment(
        reservation_id=booking_reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1200.00"),
    )

    paid_at = datetime(2028, 2, 1, 14, 30, 0)

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=belvilla_payment_id,
        paid_at=paid_at,
    )

    mark_payment_as_paid(
        connection=db_connection,
        payment_id=booking_payment_id,
        paid_at=paid_at,
    )

    report = generate_payment_report(
        connection=db_connection,
        start_date=date(2028, 2, 1),
        end_date=date(2028, 3, 1),
        vat_rate=8,
        source_code="BELVILLA",
    )

    assert len(report) == 1

    row = report[0]

    assert row["payment_id"] == belvilla_payment_id
    assert row["source_code"] == "BELVILLA"
    assert row["gross_amount"] == Decimal("900.00")