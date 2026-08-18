from datetime import date, datetime
from decimal import Decimal

from app.accounting_report_service import AccountingReportService
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository


def test_generate_monthly_accounting_report(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 7),
        guests_count=2,
        status="CONFIRMED",
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment_repository.mark_payment_as_paid(
        payment_id,
        datetime(2026, 11, 15, 10, 0, 0),
    )

    accounting_report_service = AccountingReportService(
        payment_repository=payment_repository
    )

    report = accounting_report_service.generate_monthly_report(
        2026,
        11,
    )

    assert len(report["rows"]) == 1
    assert report["rows"][0]["reservation_id"] == reservation_id
    assert report["rows"][0]["payment_type"] == "DEPOSIT"
    assert report["rows"][0]["amount"] == Decimal("500.00")
    assert report["year"] == 2026
    assert report["month"] == 11


def test_generate_monthly_report_uses_paid_at_month(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    october_reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 11, 10),
        check_out=date(2026, 11, 15),
        guests_count=2,
        status="CONFIRMED",
    )

    november_reservation_id = reservation_repository.create(
        cottage_id=2,
        source_id=1,
        check_in=date(2026, 12, 10),
        check_out=date(2026, 12, 15),
        guests_count=2,
        status="CONFIRMED",
    )

    october_payment_id = payment_repository.create_payment(
        reservation_id=october_reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("400.00"),
    )

    november_payment_id = payment_repository.create_payment(
        reservation_id=november_reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    payment_repository.mark_payment_as_paid(
        october_payment_id,
        datetime(2026, 10, 31, 23, 59, 59),
    )

    payment_repository.mark_payment_as_paid(
        november_payment_id,
        datetime(2026, 11, 1, 0, 0, 1),
    )

    accounting_report_service = AccountingReportService(
        payment_repository=payment_repository
    )

    report = accounting_report_service.generate_monthly_report(
        2026,
        11,
    )

    assert len(report["rows"]) == 1
    assert report["rows"][0]["reservation_id"] == november_reservation_id
    assert report["rows"][0]["amount"] == Decimal("500.00")

def test_generate_monthly_report_with_no_payments_returns_empty_report(
    db_connection,
):
    payment_repository = PaymentRepository(db_connection)

    accounting_report_service = AccountingReportService(
        payment_repository=payment_repository
    )

    report = accounting_report_service.generate_monthly_report(
        2026,
        11,
    )

    assert len(report["rows"]) == 0
    assert report["total_amount"] == Decimal("0.00")

def test_generate_monthly_report_with_multiple_payments(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id_1 = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 7),
        guests_count=2,
        status="CONFIRMED",
    )

    reservation_id_2 = reservation_repository.create(
        cottage_id=2,
        source_id=1,
        check_in=date(2026, 11, 10),
        check_out=date(2026, 11, 15),
        guests_count=2,
        status="CONFIRMED",
    )

    payment_id_1 = payment_repository.create_payment(
        reservation_id=reservation_id_1,
        payment_type="DEPOSIT",
        amount=Decimal("400.00"),
    )

    payment_id_2 = payment_repository.create_payment(
        reservation_id=reservation_id_2,
        payment_type="BALANCE",
        amount=Decimal("600.00"),
    )

    payment_repository.mark_payment_as_paid(
        payment_id_1,
        datetime(2026, 11, 15, 10, 0, 0),
    )

    payment_repository.mark_payment_as_paid(
        payment_id_2,
        datetime(2026, 11, 20, 15, 30, 0),
    )

    accounting_report_service = AccountingReportService(
        payment_repository=payment_repository
    )

    report = accounting_report_service.generate_monthly_report(
        2026,
        11,
    )

    assert len(report["rows"]) == 2
    assert report["total_amount"] == Decimal("1000.00")
    assert report["year"] == 2026
    assert report["month"] == 11

def test_generate_payment_report_for_date_range(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id_1 = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 7),
        guests_count=2,
        status="CONFIRMED",
    )

    reservation_id_2 = reservation_repository.create(
        cottage_id=2,
        source_id=1,
        check_in=date(2026, 11, 10),
        check_out=date(2026, 11, 15),
        guests_count=2,
        status="CONFIRMED",
    )

    payment_id_1 = payment_repository.create_payment(
        reservation_id=reservation_id_1,
        payment_type="DEPOSIT",
        amount=Decimal("400.00"),
    )

    payment_id_2 = payment_repository.create_payment(
        reservation_id=reservation_id_2,
        payment_type="BALANCE",
        amount=Decimal("600.00"),
    )

    payment_repository.mark_payment_as_paid(
        payment_id_1,
        datetime(2026, 11, 15, 10, 0, 0),
    )

    payment_repository.mark_payment_as_paid(
        payment_id_2,
        datetime(2026, 11, 25, 15, 30, 0),
    )

    accounting_report_service = AccountingReportService(
        payment_repository=payment_repository
    )

    start_date = datetime(2026, 11, 14)
    end_date = datetime(2026, 11, 21)

    report = accounting_report_service.generate_payment_report(
        start_date=start_date,
        end_date=end_date,
    )

    assert len(report["rows"]) == 1
    assert report["total_amount"] == Decimal("400.00")
    assert report["start_date"] == start_date
    assert report["end_date"] == end_date
    
def test_generate_payment_report_for_split_payments(db_connection):

    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2028, 11, 1),
        check_out=date(2028, 11, 7),
        guests_count=2,
        status="CONFIRMED",
    )

    payment_id_1 = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("400.00"),
    )

    payment_id_2 = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("600.00"),
    )

    payment_repository.mark_payment_as_paid(
        payment_id_1,
        datetime(2027, 11, 15, 10, 0, 0),
    )

    payment_repository.mark_payment_as_paid(
        payment_id_2,
        datetime(2028, 11, 1, 15, 30, 0),
    )

    accounting_report_service = AccountingReportService(
        payment_repository=payment_repository
    )

    start_date = datetime(2026, 11, 14)
    end_date = datetime(2028, 11, 21)

    report = accounting_report_service.generate_payment_report(
        start_date=start_date,
        end_date=end_date,
    )

    assert len(report["rows"]) == 2
    assert report["total_amount"] == Decimal("1000.00")
    assert report["rows"][0]["reservation_id"] == reservation_id
    assert report["rows"][1]["reservation_id"] == reservation_id
    assert report["rows"][0]["payment_type"] == "DEPOSIT"
    assert report["rows"][1]["payment_type"] == "BALANCE"
    assert report["rows"][0]["paid_at"] == datetime(2027, 11, 15, 10, 0, 0)
    assert report["rows"][1]["paid_at"] == datetime(2028, 11, 1, 15, 30, 0)



