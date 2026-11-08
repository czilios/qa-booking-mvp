from datetime import date
from decimal import Decimal

import pymysql
import pytest

from app.accounting_report_service import generate_accounting_report
from app.overall_report_service import generate_cash_flow_report
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository


pytestmark = pytest.mark.db


def test_cp2_schema_columns_and_nonunique_bank_payment_index(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, IS_NULLABLE, DATA_TYPE, COLUMN_DEFAULT "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND ((TABLE_NAME = %s AND COLUMN_NAME IN (%s, %s, %s)) "
            "OR (TABLE_NAME = %s AND COLUMN_NAME IN (%s, %s)))",
            ("customers", "phone", "email", "address", "bank_transactions", "amount", "is_test_data"),
        )
        columns = {(row["TABLE_NAME"], row["COLUMN_NAME"]): row for row in cursor.fetchall()}
        for column in ("phone", "email", "address"):
            assert columns[("customers", column)]["IS_NULLABLE"] == "YES"
        assert columns[("bank_transactions", "is_test_data")]["IS_NULLABLE"] == "NO"
        assert str(columns[("bank_transactions", "is_test_data")]["COLUMN_DEFAULT"]).strip("'") == "0"
        cursor.execute(
            "SELECT NON_UNIQUE FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s",
            ("payments", "idx_payments_bank_transaction"),
        )
        assert cursor.fetchone()["NON_UNIQUE"] == 1


@pytest.mark.parametrize("contact", ["", " ", "\t", "\r", "\n", " \t\r\n"])
def test_customer_check_rejects_whitespace_contacts_independently_of_api(db_connection, contact):
    with db_connection.cursor() as cursor:
        with pytest.raises(pymysql.MySQLError) as exc:
            cursor.execute(
                "INSERT INTO customers (first_name, last_name, phone, email, address) VALUES (%s, %s, %s, %s, %s)",
                ("Jan", "Kowalski", contact, contact, "Address alone is not contact"),
            )
        assert exc.value.args[0] == 4025


@pytest.mark.parametrize("phone,email", [("123456789", None), (None, "guest@example.com")])
def test_customer_check_accepts_one_contact_independently_of_api(db_connection, phone, email):
    with db_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO customers (first_name, last_name, phone, email) VALUES (%s, %s, %s, %s)",
            ("Jan", "Kowalski", phone, email),
        )
        assert cursor.lastrowid


@pytest.mark.parametrize(
    "linked_payments, bank_is_test, expected_cash, expected_review",
    [
        ([(False, False), (False, False)], False, True, False),
        ([(False, False), (True, False)], False, True, True),
        ([(None, False)], False, True, True),
        ([(False, False), (False, True)], False, True, True),
        ([(False, True), (False, True)], False, False, False),
        ([(False, False)], True, False, False),
    ],
)
def test_cash_and_accounting_handle_multiple_linked_payments(
    db_connection, linked_payments, bank_is_test, expected_cash, expected_review
):
    transaction_date = date(2099, 12, 12)
    start_date, end_date = date(2099, 12, 12), date(2099, 12, 13)
    baseline_total = generate_cash_flow_report(db_connection, start_date, end_date)["total_amount"]
    with db_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO bank_transactions (transaction_date, source_id, cottage_id, amount, is_test_data) VALUES (%s, %s, %s, %s, %s)",
            (transaction_date, 1, 1, Decimal("123.45"), bank_is_test),
        )
        transaction_id = cursor.lastrowid

    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)
    for invoice, is_test in linked_payments:
        reservation_id = reservation_repository.create(
            cottage_id=1,
            source_id=1,
            check_in=date(2099, 12, 15),
            check_out=date(2099, 12, 16),
            guests_count=1,
            is_test_data=is_test,
        )
        payment_repository.create_payment(
            reservation_id=reservation_id,
            payment_type="DEPOSIT",
            amount=Decimal("123.45"),
            status="PAID",
            invoice=invoice,
            bank_transaction_id=transaction_id,
        )

    cash = generate_cash_flow_report(db_connection, start_date, end_date)
    assert sum(row["id"] == transaction_id for row in cash["transactions"]) == int(expected_cash)
    assert cash["total_amount"] == baseline_total + (Decimal("123.45") if expected_cash else Decimal("0.00"))

    accounting = generate_accounting_report(db_connection, start_date, end_date)
    review = [row for row in accounting["manual_review"] if row["id"] == transaction_id]
    assert len(review) == int(expected_review)
    if expected_review:
        assert review[0]["reason"]
        assert review[0]["amount"] == Decimal("123.45")
        assert all(entry.get("transaction_id") != transaction_id for entry in accounting["entries"])