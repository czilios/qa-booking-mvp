
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.bank_transaction_repository import BankTransactionRepository
from datetime import date
from decimal import Decimal 
from app.payment_service import sync_payments


def test_sync_payment_creates_paid_payment_from_bank_transaction(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        total_amount=Decimal("1700.00"),
        status="CONFIRMED",
        invoice_number="TEST-INV-001",
    )

    bank_transaction_id = BankTransactionRepository(
        db_connection
    ).create(
        transaction_date=date(2026, 7, 7),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1700.00"),
        notes="TEST-INV-001",
    )

    sync_payments(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    payments = payment_repository.get_payment_by_reservation_id(
        reservation_id
    )

    assert len(payments) == 1

    payment = payments[0]

    assert payment["reservation_id"] == reservation_id
    assert payment["amount"] == Decimal("1700.00")
    assert payment["status"] == "PAID"
    assert payment["bank_transaction_id"] == bank_transaction_id

def test_sync_payment_does_not_create_payment_if_amount_mismatch(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        total_amount=Decimal("1700.00"),
        status="CONFIRMED",
        invoice_number="TEST-INV-002",
    )

    BankTransactionRepository(
        db_connection
    ).create(
        transaction_date=date(2026, 7, 7),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1600.00"),
        notes="TEST-INV-002",
    )

    sync_payments(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    payments = payment_repository.get_payment_by_reservation_id(
        reservation_id
    )

    assert len(payments) == 0  

def test_sync_payment_does_not_create_payment_if_no_invoice_number(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        total_amount=Decimal("1700.00"),
        status="CONFIRMED",
    )

    BankTransactionRepository(
        db_connection
    ).create(
        transaction_date=date(2026, 7, 7),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1700.00"),
        notes="TEST-INV-003",
    )

    sync_payments(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    payments = payment_repository.get_payment_by_reservation_id(
        reservation_id
    )

    assert len(payments) == 0   
def test_sync_payment_for_the_same_bank_transaction_id(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        total_amount=Decimal("1700.00"),
        status="CONFIRMED",
        invoice_number="TEST-INV-004",
    )

    bank_transaction_id = BankTransactionRepository(
        db_connection
    ).create(
        transaction_date=date(2026, 7, 7),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1700.00"),
        notes="TEST-INV-004",
    )  
    assert bank_transaction_id is not None
    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("1700.00"),
        status="UNPAID",
        due_at=date(2026, 8, 3),
        invoice=True,
        bank_transaction_id=bank_transaction_id,
    )
    assert payment_id is not None  
    # Attempt to sync payments again to see if it creates a duplicate payment
    sync_payments(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    payments = payment_repository.get_payment_by_reservation_id(
        reservation_id
    )

    # There should still be only one payment for the same bank transaction ID
    assert len(payments) == 1   

def test_sync_payment_creates_paid_paymentfor_Belvilla_from_bank_transaction(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=4,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        total_amount=Decimal("1700.00"),
        status="CONFIRMED",
        invoice_number=None,
        external_reservation_id="TEST-BELVILLA-001",
    )

    bank_transaction_id = BankTransactionRepository(
        db_connection
    ).create(
        transaction_date=date(2026, 7, 7),
        source_id=4,
        cottage_id=1,
        amount=Decimal("1700.00"),
        notes="TEST-BELVILLA-001",
    )

    sync_payments(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    payments = payment_repository.get_payment_by_reservation_id(
        reservation_id
    )

    assert len(payments) == 1

    payment = payments[0]

    assert payment["reservation_id"] == reservation_id
    assert payment["amount"] == Decimal("1700.00")
    assert payment["status"] == "PAID"
    assert payment["bank_transaction_id"] == bank_transaction_id

