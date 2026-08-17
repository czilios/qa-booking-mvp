from datetime import datetime
from decimal import Decimal

from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository

def test_payment_repository_creates_payment(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=datetime(2026, 11, 1),
        check_out=datetime(2026, 11, 7),
        guests_count=2,
        status="PENDING",
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment is not None
    assert payment["id"] == payment_id
    assert payment["reservation_id"] == reservation_id
    assert payment["type"] == "DEPOSIT"
    assert payment["amount"] == Decimal("500.00")
    assert payment["status"] == "UNPAID"
def test_get_payment_by_reservation_id(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=datetime(2026, 11, 10),
        check_out=datetime(2026, 11, 15),
        guests_count=2,
    )

    payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1000.00"),
    )

    payments = payment_repository.get_payment_by_reservation_id(
        reservation_id
    )

    assert len(payments) == 2
    assert payments[0]["type"] == "DEPOSIT"
    assert payments[1]["type"] == "BALANCE"

def test_get_deposit_payment_by_reservation_id(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=datetime(2026, 11, 20),
        check_out=datetime(2026, 11, 25),
        guests_count=2,
    )

    payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("1000.00"),
    )

    deposit = payment_repository.get_deposit_payment_by_reservation_id(
        reservation_id
    )

    assert deposit is not None
    assert deposit["reservation_id"] == reservation_id
    assert deposit["type"] == "DEPOSIT"
    assert deposit["amount"] == Decimal("500.00")
    assert deposit["status"] == "UNPAID"
def test_mark_payment_as_paid(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=datetime(2026, 12, 1),
        check_out=datetime(2026, 12, 7),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    paid_at = datetime(2026, 8, 17, 18, 30, 0)

    payment_repository.mark_payment_as_paid(
        payment_id,
        paid_at,
    )

    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment["status"] == "PAID"
    assert payment["paid_at"] == paid_at