from datetime import date
from decimal import Decimal

from app.accounting_report_service import generate_accounting_report, generate_accounting_reports
from app.overall_report_service import generate_cash_flow_report
from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository
from tests.conftest import created_bank_transaction_cleanup



def test_accounting_report_calculates_direct_income(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2044, 7, 15),
        source_id=1,  # DIRECT
        cottage_id=1,
        amount=Decimal("1080.00"),
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("1080.00")
    assert report["total_net"] == Decimal("1000.00")
    assert report["total_vat"] == Decimal("80.00")

def test_accounting_report_respects_date_boundaries(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transactions = [
        (date(2044, 6, 30), Decimal("100.00")),
        (date(2044, 7, 1), Decimal("200.00")),
        (date(2044, 7, 31), Decimal("300.00")),
        (date(2044, 8, 1), Decimal("400.00")),
    ]

    created_ids = []

    for transaction_date, amount in transactions:
        transaction_id = repository.create(
            transaction_date=transaction_date,
            source_id=1,
            cottage_id=1,
            amount=amount,
        )
        created_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(created_ids)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("500.00")
    assert report["total_net"] == Decimal("462.96")
    assert report["total_vat"] == Decimal("37.04")

def test_accounting_report_includes_only_direct_bank_transactions(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transactions = [
        (date(2044, 7, 10), 1, Decimal("1080.00")),
        (date(2044, 7, 11), 2, Decimal("850.00")),
        (date(2044, 7, 12), 4, Decimal("1200.00")),
    ]

    created_ids = []

    for transaction_date, source_id, amount in transactions:
        transaction_id = repository.create(
            transaction_date=transaction_date,
            source_id=source_id,
            cottage_id=1,
            amount=amount,
        )

        created_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(created_ids)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("1080.00")
    assert report["total_net"] == Decimal("1000.00")
    assert report["total_vat"] == Decimal("80.00")

    assert len(report["transactions"]) == 1
    assert report["transactions"][0]["source_id"] == 1


def test_accounting_report_includes_confirmed_booking_by_check_in(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 22),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert len(report["booking_reservations"]) == 1

    reservation = report["booking_reservations"][0]

    assert reservation["id"] == reservation_id
    assert reservation["total_amount"] == Decimal("1000.00")

def test_accounting_report_isolates_booking_from_direct_and_belvilla(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    booking_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 10),
        check_out=date(2044, 7, 15),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        accounting_included=True,
    )

    direct_id = repository.create(
        cottage_id=2,
        source_id=1,  # DIRECT
        check_in=date(2044, 7, 11),
        check_out=date(2044, 7, 16),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2000.00"),
    )

    belvilla_id = repository.create(
        cottage_id=3,
        source_id=4,  # BELVILLA
        check_in=date(2044, 7, 12),
        check_out=date(2044, 7, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("3000.00"),
    )

    created_reservation_cleanup["reservation_ids"].extend(
        [
            booking_id,
            direct_id,
            belvilla_id,
        ]
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    booking_ids = {
        reservation["id"]
        for reservation in report["booking_reservations"]
    }

    assert booking_id in booking_ids
    assert direct_id not in booking_ids
    assert belvilla_id not in booking_ids

def test_accounting_report_calculates_booking_gross_with_commission(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("850.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    booking = report["booking_reservations"][0]

    assert booking["id"] == reservation_id
    assert booking["total_amount"] == Decimal("850.00")
    assert booking["commission_amount"] == Decimal("150.00")
    assert booking["gross_amount"] == Decimal("1000.00")

def test_accounting_report_calculates_booking_gross_without_commission(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    booking = report["booking_reservations"][0]

    assert booking["id"] == reservation_id
    assert booking["total_amount"] == Decimal("1000.00")
    assert booking["commission_amount"] is None
    assert booking["gross_amount"] == Decimal("1000.00")

def test_accounting_report_includes_booking_gross_in_total(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("850.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(reservation_id)
    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("1000.00")

def test_accounting_report_calculates_net_and_vat_from_booking_gross(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("850.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(reservation_id)
    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("1000.00")
    assert report["total_net"] == Decimal("925.93")
    assert report["total_vat"] == Decimal("74.07")

def test_accounting_report_excludes_booking_outside_period(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 8, 1),
        check_out=date(2044, 8, 5),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not report["booking_reservations"]

def test_accounting_report_excludes_CANCELLED_reservations(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CANCELLED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not report["booking_reservations"]

def test_accounting_report_excludes_non_accounting_reservations(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not report["booking_reservations"]

def test_accounting_report_excludes_direct_non_accounting_reservation(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=1,  # DIRECT
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        accounting_included=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not any(
        transaction["amount"] == Decimal("1000.00")
        for transaction in report["transactions"]
    )
def test_accounting_report_excludes_confirmed_belvilla_even_if_accounting_included(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=4,  # BELVILLA
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not any(
        reservation["id"] == reservation_id
        for reservation in report["booking_reservations"]
    )
def test_accounting_report_total_gross_includes_direct_and_booking(
    db_connection,
    created_reservation_cleanup,
    created_bank_transaction_cleanup,
):
    bank_transaction_repository = BankTransactionRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)

    transaction_id = bank_transaction_repository.create(
    transaction_date=date(2044, 7, 15),
    source_id=1,
    cottage_id=1,
    amount=Decimal("500.00"),
    notes="testing",
)

    created_bank_transaction_cleanup.append(transaction_id)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("850.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )
    for booking in report["booking_reservations"]:
        print(
            "BOOKING:",
            booking["id"],
            booking["check_in"],
            booking["total_amount"],
            booking["commission_amount"],
            booking["accounting_included"],
        )
    print("DIRECT:", report["transactions"])
    print("TOTAL:", report["total_gross"])
    assert report["total_gross"] == Decimal("1500.00")

def test_accounting_report_includes_direct_bank_transaction_even_if_reservation_is_non_accounting(
    db_connection,
    created_reservation_cleanup,
    created_bank_transaction_cleanup,
):
    bank_transaction_repository = BankTransactionRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,  # DIRECT
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        accounting_included=False,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    transaction_id = bank_transaction_repository.create(
        transaction_date=date(2044, 7, 15),
        source_id=1,  # DIRECT
        cottage_id=1,
        amount=Decimal("1080.00"),
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("1080.00")

def test_accounting_report_sums_multiple_direct_bank_transactions(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_ids = []

    for amount in (
        Decimal("500.00"),
        Decimal("750.00"),
        Decimal("1080.00"),
    ):
        transaction_id = repository.create(
            transaction_date=date(2044, 7, 15),
            source_id=1,  # DIRECT
            cottage_id=1,
            amount=amount,
        )
        transaction_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(transaction_ids)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert report["total_gross"] == Decimal("2330.00")

def test_accounting_report_sums_multiple_direct_and_booking_transactions(
    db_connection,
    created_reservation_cleanup,
    created_bank_transaction_cleanup,
):
    bank_transaction_repository = BankTransactionRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)

    direct_amounts = (
        Decimal("500.00"),
        Decimal("750.00"),
    )

    direct_ids = []

    for amount in direct_amounts:
        transaction_id = bank_transaction_repository.create(
            transaction_date=date(2044, 7, 15),
            source_id=1,  # DIRECT
            cottage_id=1,
            amount=amount,
        )
        direct_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(direct_ids)

    booking_data = (
        (Decimal("850.00"), Decimal("150.00")),
        (Decimal("900.00"), Decimal("100.00")),
    )

    booking_ids = []

    for total_amount, commission_amount in booking_data:
        reservation_id = reservation_repository.create(
            cottage_id=1,
            source_id=2,  # BOOKING
            check_in=date(2044, 7, 15),
            check_out=date(2044, 7, 20),
            guests_count=2,
            status="CONFIRMED",
            total_amount=total_amount,
            commission_amount=commission_amount,
            accounting_included=True,
        )
        booking_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(booking_ids)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    # Direct: 500 + 750 = 1250
    # Booking: (850 + 150) + (900 + 100) = 2000
    # Total = 3250
    assert report["total_gross"] == Decimal("3250.00")

def test_accounting_report_returns_zero_for_empty_period(
    db_connection,
):
    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2040, 1, 1),
        end_date=date(2040, 2, 1),
    )

    assert report["total_gross"] == Decimal("0.00")
    assert report["total_net"] == Decimal("0.00")
    assert report["total_vat"] == Decimal("0.00")
    assert not report["transactions"]
    assert not report["booking_reservations"]

def test_accounting_report_respects_booking_check_in_boundaries(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservations = [
        (date(2044, 6, 30), date(2044, 7, 2), Decimal("1000.00")),
        (date(2044, 7, 1), date(2044, 7, 3), Decimal("1100.00")),
        (date(2044, 7, 31), date(2044, 8, 2), Decimal("1200.00")),
        (date(2044, 8, 1), date(2044, 8, 3), Decimal("1300.00")),
    ]

    created_ids = []

    for check_in, check_out, amount in reservations:
        reservation_id = repository.create(
            cottage_id=1,
            source_id=2,  # BOOKING
            check_in=check_in,
            check_out=check_out,
            guests_count=2,
            status="CONFIRMED",
            total_amount=amount,
            accounting_included=True,
        )

        created_ids.append(reservation_id)

    created_reservation_cleanup["reservation_ids"].extend(created_ids)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    booking_ids = {
        reservation["id"]
        for reservation in report["booking_reservations"]
    }

    assert created_ids[0] not in booking_ids
    assert created_ids[1] in booking_ids
    assert created_ids[2] in booking_ids
    assert created_ids[3] not in booking_ids

def test_accounting_report_excludes_pending_booking(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="PENDING",
        total_amount=Decimal("1000.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not report["booking_reservations"]

def test_accounting_report_excludes_cancelled_booking(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CANCELLED",
        total_amount=Decimal("1000.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not report["booking_reservations"]

def test_accounting_report_excludes_expired_booking(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 6, 15),
        check_out=date(2044, 6, 20),
        guests_count=2,
        status="EXPIRED",
        total_amount=Decimal("1000.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not report["booking_reservations"]   

def test_accounting_report_calculates_booking_gross_with_zero_commission(
    db_connection,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,  # BOOKING
        check_in=date(2044, 7, 15),
        check_out=date(2044, 7, 20),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("0.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    booking = report["booking_reservations"][0]

    assert booking["gross_amount"] == Decimal("1000.00")

def test_accounting_reports_calculate_carry_between_months(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transactions = [
        (date(2044, 6, 15), Decimal("100.00")),
        (date(2044, 7, 15), Decimal("200.00")),
        (date(2044, 8, 15), Decimal("300.00")),
    ]

    created_ids = []

    for transaction_date, amount in transactions:
        transaction_id = repository.create(
            transaction_date=transaction_date,
            source_id=1,
            cottage_id=1,
            amount=amount,
        )
        created_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(created_ids)

    db_connection.commit()

    reports = generate_accounting_reports(
        connection=db_connection,
        start_date=date(2044, 6, 1),
        end_date=date(2044, 9, 1),
    )

    assert reports[0]["total_gross"] == Decimal("100.00")
    assert reports[0]["carry_amount"] == Decimal("0.00")
    assert reports[0]["grand_total"] == Decimal("100.00")

    assert reports[1]["total_gross"] == Decimal("200.00")
    assert reports[1]["carry_amount"] == Decimal("100.00")
    assert reports[1]["grand_total"] == Decimal("300.00")

    assert reports[2]["total_gross"] == Decimal("300.00")
    assert reports[2]["carry_amount"] == Decimal("300.00")
    assert reports[2]["grand_total"] == Decimal("600.00")

def test_accounting_reports_carry_survives_empty_month(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transactions = [
        (date(2044, 6, 15), Decimal("100.00")),
        (date(2044, 8, 15), Decimal("300.00")),
    ]

    created_ids = []

    for transaction_date, amount in transactions:
        transaction_id = repository.create(
            transaction_date=transaction_date,
            source_id=1,
            cottage_id=1,
            amount=amount,
        )
        created_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(created_ids)

    db_connection.commit()

    reports = generate_accounting_reports(
        connection=db_connection,
        start_date=date(2044, 6, 1),
        end_date=date(2044, 9, 1),
    )

    # Czerwiec
    assert reports[0]["total_gross"] == Decimal("100.00")
    assert reports[0]["carry_amount"] == Decimal("0.00")
    assert reports[0]["grand_total"] == Decimal("100.00")

    # Lipiec — brak przychodów
    assert reports[1]["total_gross"] == Decimal("0.00")
    assert reports[1]["carry_amount"] == Decimal("100.00")
    assert reports[1]["grand_total"] == Decimal("100.00")

    # Sierpień
    assert reports[2]["total_gross"] == Decimal("300.00")
    assert reports[2]["carry_amount"] == Decimal("100.00")
    assert reports[2]["grand_total"] == Decimal("400.00")

def test_accounting_report_entries_are_sorted_by_date(
    db_connection,
    created_bank_transaction_cleanup,
    created_reservation_cleanup,
):
    # Direct: 10.07.2044
    transaction_id = BankTransactionRepository(db_connection).create(
        transaction_date=date(2044, 7, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1000.00"),
    )

    created_bank_transaction_cleanup.append(transaction_id)

    # Booking: check-in 03.07.2032
    reservation_id = ReservationRepository(db_connection).create(
        cottage_id=1,
        source_id=2,
        check_in=date(2044, 7, 3),
        check_out=date(2044, 7, 7),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("2000.00"),
        accounting_included=True,
        commission_amount=Decimal("200.00"),
    )

    created_reservation_cleanup["reservation_ids"].append(reservation_id)

    db_connection.commit()

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    entries = [
            entry
            for entry in report["entries"]
            if entry.get("transaction_id") == transaction_id
            or entry.get("reservation_id") == reservation_id
    ]

    assert [entry["source"] for entry in entries] == [
        "Booking",
        "Direct",
    ]

    assert [entry["date"] for entry in entries] == [
        date(2044, 7, 3),
        date(2044, 7, 10),
    ]

def test_accounting_report_excludes_direct_transaction_with_invoice(
    db_connection,
    created_bank_transaction_cleanup,
    created_reservation_cleanup,
):
    reservation_id = ReservationRepository(db_connection).create(
        cottage_id=6,
        source_id=1,
        check_in=date(2044, 8, 3),
        check_out=date(2044, 8, 9),
        guests_count=1,
        status="CONFIRMED",
        total_amount=Decimal("1777.00"),
        accounting_included=True,
        invoice_number="TEST/1/2044",
    )

    transaction_id = BankTransactionRepository(db_connection).create(
        transaction_date=date(2044, 7, 7),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1777.00"),
        notes="TEST/1/2044",
    )

    payment_id = PaymentRepository(db_connection).create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("1777.00"),
        status="PAID",
        invoice=True,
        bank_transaction_id=transaction_id,
    )

    created_reservation_cleanup["reservation_ids"].append(reservation_id)
    created_bank_transaction_cleanup.append(transaction_id)

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )

    assert not any(
        entry["gross_amount"] == Decimal("1777.00")
        and entry["source"] == "Direct"
        for entry in report["entries"]
    )


def test_accounting_report_matches_invoice_number_and_amount_before_excluding_direct(
    db_connection,
    created_bank_transaction_cleanup,
    created_reservation_cleanup,
):
    invoice_number = "TEST/EXACT-MATCH/2044"
    reservation_id = ReservationRepository(db_connection).create(
        cottage_id=6,
        source_id=1,
        check_in=date(2044, 8, 3),
        check_out=date(2044, 8, 9),
        guests_count=1,
        status="CONFIRMED",
        total_amount=Decimal("1777.00"),
        accounting_included=True,
        invoice_number=invoice_number,
    )
    bank_repository = BankTransactionRepository(db_connection)
    transaction_ids = {
        "matching": bank_repository.create(
            transaction_date=date(2044, 7, 7),
            source_id=1,
            cottage_id=None,
            amount=Decimal("1777.00"),
            notes=invoice_number,
        ),
        "different_invoice": bank_repository.create(
            transaction_date=date(2044, 7, 8),
            source_id=1,
            cottage_id=None,
            amount=Decimal("1777.00"),
            notes="TEST/OTHER-INVOICE/2044",
        ),
        "different_amount": bank_repository.create(
            transaction_date=date(2044, 7, 9),
            source_id=1,
            cottage_id=None,
            amount=Decimal("1000.00"),
            notes=invoice_number,
        ),
    }
    created_reservation_cleanup["reservation_ids"].append(reservation_id)
    created_bank_transaction_cleanup.extend(transaction_ids.values())

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2044, 7, 1),
        end_date=date(2044, 8, 1),
    )
    reported_transaction_ids = {
        transaction["id"] for transaction in report["transactions"]
    }

    assert transaction_ids["matching"] not in reported_transaction_ids
    assert transaction_ids["different_invoice"] in reported_transaction_ids
    assert transaction_ids["different_amount"] in reported_transaction_ids


def test_actual_direct_invoice_transaction_8333_is_excluded_only_from_accounting(
    db_connection,
):
    bank_repository = BankTransactionRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    transaction = bank_repository.get_by_id(8333)
    assert transaction is not None
    assert transaction["transaction_date"] == date(2026, 7, 7)
    assert transaction["amount"] == Decimal("1700.00")
    assert transaction["notes"] == "1/W/2026"

    matching_reservations = reservation_repository.get_by_invoice_number(
        transaction["notes"]
    )
    assert any(
        reservation["id"] == 16594
        and reservation["invoice_number"] == transaction["notes"]
        and reservation["total_amount"] == transaction["amount"]
        for reservation in matching_reservations
    )
    assert payment_repository.get_payment_by_bank_transaction_id(8333) is None

    accounting_report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )
    assert not any(
        accounting_transaction["id"] == 8333
        for accounting_transaction in accounting_report["transactions"]
    )
    assert not any(
        entry.get("transaction_id") == 8333
        for entry in accounting_report["entries"]
    )

    cash_flow_report = generate_cash_flow_report(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )
    assert any(
        cash_flow_transaction["id"] == 8333
        for cash_flow_transaction in cash_flow_report["transactions"]
    )


def test_actual_booking_6431_is_accounted_in_check_in_month(db_connection):
    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    booking = next(
        booking
        for booking in report["booking_reservations"]
        if booking["id"] == 6431
    )
    assert booking["check_in"] == date(2026, 7, 31)
    assert booking["total_amount"] == Decimal("899.10")
    assert any(
        entry.get("reservation_id") == 6431
        and entry["date"] == date(2026, 7, 31)
        and entry["gross_amount"] == Decimal("899.10")
        for entry in report["entries"]
    )
