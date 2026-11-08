from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from jinja2 import Environment, FileSystemLoader

from app import accounting_report_service, overall_report_service, payment_service, sales_report_service
from app.bank_statement_service import BankStatementReportService
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository


START = date(2026, 1, 1)
END = date(2026, 2, 1)


class RecordingCursor:
    def __init__(self, rows=()):
        self.rows = rows
        self.query = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.query = " ".join(query.split())
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=()):
        self.recording_cursor = RecordingCursor(rows)

    def cursor(self):
        return self.recording_cursor


def test_accounting_booking_query_excludes_test_reservations():
    connection = FakeConnection()
    ReservationRepository(connection).get_accounting_booking_reservations_by_check_in_between(
        date(2026, 1, 1), date(2026, 2, 1)
    )
    assert "r.is_test_data = FALSE" in connection.recording_cursor.query
    assert "r.source_id = 2" in connection.recording_cursor.query
    assert "r.accounting_included = TRUE" in connection.recording_cursor.query


def test_bank_statement_reservation_query_excludes_test_reservations():
    connection = FakeConnection()
    ReservationRepository(connection).get_confirmed_reservations_between(START, END)
    query = connection.recording_cursor.query
    assert "status = 'CONFIRMED'" in query
    assert "accounting_included = TRUE" in query
    assert "is_test_data = FALSE" in query
    assert "check_out >= %s" in query
    assert "check_out < %s" in query


def test_bank_report_query_filters_without_multiplying_transactions():
    connection = FakeConnection()
    BankTransactionRepository(connection).list_report_by_date_range(START, END, "INV")
    query = connection.recording_cursor.query
    assert "b.is_test_data = FALSE" in query
    assert "NOT EXISTS (SELECT 1 FROM payments p" in query
    assert "OR EXISTS (SELECT 1 FROM payments p JOIN reservations r" in query
    assert "r.is_test_data = FALSE" in query
    assert "FROM bank_transactions b WHERE" in query
    assert "b.transaction_date >= %s AND b.transaction_date < %s" in query
    assert "b.notes = %s" in query
    assert connection.recording_cursor.params == [START, END, "INV"]


def test_bank_transaction_repository_can_mark_test_data():
    connection = FakeConnection()
    connection.recording_cursor.lastrowid = 7
    result = BankTransactionRepository(connection).create(
        transaction_date=START,
        source_id=1,
        cottage_id=None,
        amount=Decimal("10.00"),
        is_test_data=True,
    )
    assert result == 7
    assert "is_test_data" in connection.recording_cursor.query
    assert connection.recording_cursor.params[-1] is True


@pytest.mark.parametrize("method,args", [
    ("get_paid_payments_between", (START, END)),
    ("get_paid_payments_for_month", (2026, 1)),
    ("get_paid_amount_by_reservation_ids", ([1, 2],)),
])
def test_payment_report_queries_exclude_test_reservations_and_bank_transactions(method, args):
    connection = FakeConnection()
    getattr(PaymentRepository(connection), method)(*args)
    query = connection.recording_cursor.query
    assert "r.is_test_data = FALSE" in query
    assert "p.bank_transaction_id IS NULL OR EXISTS" in query
    assert "b.is_test_data = FALSE" in query
    if method == "get_paid_amount_by_reservation_ids":
        assert "'PAID', 'FORFEITED', 'REFUNDED'" in query
        assert "WHEN p.status = 'REFUNDED' THEN -p.amount" in query


def test_reservation_queries_apply_report_filters_without_changing_default():
    connection = FakeConnection()
    repository = ReservationRepository(connection)
    repository.get_all_confirmed_reservations_between(START, END)
    assert "is_test_data = FALSE" not in connection.recording_cursor.query
    repository.get_all_confirmed_reservations_between(START, END, exclude_test_data=True)
    assert "is_test_data = FALSE" in connection.recording_cursor.query
    repository.get_confirmed_reservations_by_created_at_between(START, END)
    assert "r.is_test_data = FALSE" in connection.recording_cursor.query
    repository.get_by_invoice_number("INV")
    assert "is_test_data" in connection.recording_cursor.query


def test_accounting_fetches_all_linked_payments_with_flags():
    connection = FakeConnection()
    PaymentRepository(connection).get_payments_with_reservation_flags_by_bank_transaction_id(7)
    query = connection.recording_cursor.query
    assert "r.is_test_data" in query
    assert "p.bank_transaction_id = %s" in query
    assert "LIMIT" not in query
    assert connection.recording_cursor.params == (7,)


def transaction(transaction_id, amount="108.00", source=1, notes=None):
    return {
        "id": transaction_id,
        "source_id": source,
        "transaction_date": START,
        "amount": Decimal(amount),
        "notes": notes,
    }


def payment(invoice, is_test_data=False, status="PAID"):
    return {"invoice": invoice, "is_test_data": is_test_data, "status": status}


def accounting_report(monkeypatch, transactions, payments, reservations=(), invoices=None):
    class FakeBankRepository:
        def __init__(self, connection):
            pass

        def list_report_by_date_range(self, **kwargs):
            return transactions

    class FakePaymentRepository:
        def __init__(self, connection):
            pass

        def get_payments_with_reservation_flags_by_bank_transaction_id(self, transaction_id):
            return payments.get(transaction_id, [])

    class FakeReservationRepository:
        def __init__(self, connection):
            pass

        def get_by_invoice_number(self, number):
            return (invoices or {}).get(number, [])

        def get_accounting_booking_reservations_by_check_in_between(self, **kwargs):
            return list(reservations)

    monkeypatch.setattr(accounting_report_service, "BankTransactionRepository", FakeBankRepository)
    monkeypatch.setattr(accounting_report_service, "PaymentRepository", FakePaymentRepository)
    monkeypatch.setattr(accounting_report_service, "ReservationRepository", FakeReservationRepository)
    return accounting_report_service.generate_accounting_report(None, START, END)


@pytest.mark.parametrize("payments,reason", [
    ([payment(None)], "Brak informacji"),
    ([payment(False), payment(True)], "Różne flagi faktury"),
    ([payment(False), payment(False, True)], "testowe i rzeczywiste"),
    ([payment(None, True), payment(True)], "Brak informacji"),
])
def test_accounting_ambiguous_payments_require_manual_review(monkeypatch, payments, reason):
    report = accounting_report(monkeypatch, [transaction(1)], {1: payments})
    assert report["total_gross"] == Decimal("0.00")
    assert report["entries"] == []
    assert report["transactions"] == []
    assert report["manual_review"][0]["amount"] == Decimal("108.00")
    assert reason in report["manual_review"][0]["reason"]


def test_accounting_reports_all_applicable_manual_review_reasons(monkeypatch):
    report = accounting_report(monkeypatch, [transaction(1)], {
        1: [payment(None), payment(False), payment(True, True)],
    })
    reason = report["manual_review"][0]["reason"]
    assert "Brak informacji" in reason
    assert "Różne flagi faktury" in reason
    assert "testowe i rzeczywiste" in reason
    assert report["total_gross"] == report["total_net"] == report["total_vat"] == 0


def test_accounting_preserves_invoice_booking_and_belvilla_rules(monkeypatch):
    transactions = [
        transaction(1), transaction(2), transaction(3, notes="REAL"),
        transaction(4, notes="TEST"), transaction(5, source=4),
        transaction(6),
    ]
    invoices = {
        "REAL": [{"source_id": 1, "is_test_data": False, "invoice_number": "REAL", "total_amount": Decimal("108.00")}],
        "TEST": [{"source_id": 1, "is_test_data": True, "invoice_number": "TEST", "total_amount": Decimal("108.00")}],
    }
    bookings = [{"id": 9, "check_in": START, "total_amount": Decimal("85.00"), "commission_amount": Decimal("23.00")}]
    report = accounting_report(monkeypatch, transactions, {
        1: [payment(True), payment(True)],
        2: [payment(False), payment(False)],
        6: [payment(True, status="UNPAID")],
    }, bookings, invoices)
    assert [item["id"] for item in report["transactions"]] == [2, 4, 6]
    assert report["total_gross"] == Decimal("432.00")
    assert report["total_net"] == Decimal("400.00")
    assert report["total_vat"] == Decimal("32.00")
    assert report["manual_review"] == []
    assert report["booking_reservations"][0]["gross_amount"] == Decimal("108.00")


def test_cash_flow_uses_report_transactions_once(monkeypatch):
    class FakeReservations:
        def __init__(self, connection):
            pass

        def get_all_confirmed_reservations_between(self, **kwargs):
            assert kwargs["exclude_test_data"] is True
            return []

    class FakeBank:
        def __init__(self, connection):
            pass

        def list_report_by_date_range(self, **kwargs):
            return [transaction(1), transaction(2, "54.00", source=4)]

    monkeypatch.setattr(overall_report_service, "ReservationRepository", FakeReservations)
    monkeypatch.setattr(overall_report_service, "BankTransactionRepository", FakeBank)
    report = overall_report_service.generate_cash_flow_report(None, START, END)
    assert [row["id"] for row in report["transactions"]] == [1, 2]
    assert report["total_amount"] == Decimal("162.00")
    assert report["transactions"][1]["source_name"] == "Belvilla"


def test_sales_calculates_balance_from_filtered_reservations(monkeypatch):
    class FakeReservations:
        def __init__(self, connection):
            pass

        def get_confirmed_reservations_by_created_at_between(self, **kwargs):
            return [{"id": 1, "source_id": 2, "total_amount": Decimal("100.00")}]

    class FakePayments:
        def __init__(self, connection):
            pass

        def get_paid_amount_by_reservation_ids(self, reservation_ids):
            assert reservation_ids == [1]
            return {1: Decimal("30.00")}

    monkeypatch.setattr(sales_report_service, "ReservationRepository", FakeReservations)
    monkeypatch.setattr(sales_report_service, "PaymentRepository", FakePayments)
    report = sales_report_service.generate_sales_report(None, START, END)
    assert report["total_amount"] == Decimal("100.00")
    assert report["reservations"][0]["balance"] == Decimal("70.00")


def test_bank_statement_uses_filtered_bank_report_query():
    class FakeBank:
        def list_report_by_date_range(self, start_date, end_date, notes):
            return [transaction(1)] if start_date == START else []

    report = BankStatementReportService(None).generate_bank_statement_report(FakeBank(), 2026)
    assert report["total_gross"] == Decimal("108.00")


def test_payment_and_statement_rows_share_filtered_payment_query(monkeypatch):
    row = {
        "payment_id": 1, "reservation_id": 2, "payment_type": "DEPOSIT",
        "amount": Decimal("108.00"), "paid_at": START, "cottage_id": 1,
        "check_in": START, "check_out": END, "source_code": "DIRECT", "source_name": "Direct",
    }
    repository = Mock()
    repository.get_paid_payments_between.return_value = [row]
    monkeypatch.setattr(payment_service, "PaymentRepository", lambda connection: repository)
    payment_rows = payment_service.generate_payment_report(None, START, END, Decimal("8"))
    statement = BankStatementReportService(repository).generate_payment_report(START, END)
    assert payment_rows[0]["gross_amount"] == Decimal("108.00")
    assert payment_rows[0]["net_amount"] == Decimal("100.00")
    assert statement["rows"][0]["payment_id"] == 1
    assert statement["total_amount"] == Decimal("108.00")
    assert repository.get_paid_payments_between.call_count == 2


def test_manual_review_is_shown_in_template_and_excluded_from_carry(monkeypatch):
    report = accounting_report(monkeypatch, [transaction(1)], {1: [payment(None)]})
    monkeypatch.setattr(accounting_report_service, "generate_accounting_report", lambda **kwargs: dict(report))
    reports = accounting_report_service.generate_accounting_reports(None, START, date(2026, 3, 1))
    assert [item["grand_total"] for item in reports] == [Decimal("0.00"), Decimal("0.00")]
    assert reports[1]["carry_amount"] == Decimal("0.00")

    template_dir = Path(__file__).resolve().parents[1] / "app" / "templates"
    environment = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    html = environment.get_template("accounting_report.html").render(
        reports=reports, years=[2026], year=2026, month=0,
        url_for=lambda *args, **kwargs: "/static/styles.css",
    )
    assert "Wymaga ręcznej weryfikacji" in html
    assert "Brak informacji o fakturze" in html
    assert "108,00 zł" in html