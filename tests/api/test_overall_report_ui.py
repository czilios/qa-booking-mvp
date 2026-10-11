from datetime import date
from decimal import Decimal

from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.reservation_repository import ReservationRepository


def test_overall_report_ui_displays_bank_transaction_in_transaction_month(
    db_connection,
    api_client,
    created_reservation_cleanup,
    created_bank_transaction_cleanup,
):
    invoice_number = "TEST-CASHFLOW-UI-JUL-2026"
    reservation_id = ReservationRepository(db_connection).create(
        cottage_id=1,
        source_id=1,
        check_in=date(2026, 8, 3),
        check_out=date(2026, 8, 9),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1700.00"),
        invoice_number=invoice_number,
    )
    created_reservation_cleanup["reservation_ids"].append(reservation_id)

    transaction_id = BankTransactionRepository(db_connection).create(
        transaction_date=date(2026, 7, 7),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1700.00"),
        description="TEST-CASHFLOW-UI-JUL-2026 bank deposit",
        notes=invoice_number,
    )
    created_bank_transaction_cleanup.append(transaction_id)
    db_connection.commit()

    response = api_client.get(
        "/ui/reports/overall",
        params={"month": 7, "year": 2026},
    )

    assert response.status_code == 200
    assert "TEST-CASHFLOW-UI-JUL-2026 bank deposit" in response.text
    assert "1 700,00 zł" in response.text


def test_overall_report_ui_displays_full_year_cash_flow(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    transaction_id = BankTransactionRepository(db_connection).create(
        transaction_date=date(2026, 12, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("850.00"),
        description="TEST-CASHFLOW-YEAR-2026 deposit",
    )
    created_bank_transaction_cleanup.append(transaction_id)
    db_connection.commit()

    response = api_client.get(
        "/ui/reports/overall",
        params={"month": 0, "year": 2026},
    )

    assert response.status_code == 200
    assert "TEST-CASHFLOW-YEAR-2026 deposit" in response.text
    assert "850,00 zł" in response.text
