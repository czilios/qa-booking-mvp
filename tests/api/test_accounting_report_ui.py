from datetime import date
from decimal import Decimal

import pytest

from app.accounting_report_service import generate_accounting_report
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.reservation_repository import ReservationRepository


def test_accounting_report_ui_returns_200(api_client):
    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 7,
            "year": 2026,
        },
    )

    assert response.status_code == 200

def test_accounting_report_ui_displays_direct_transaction(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2032, 10, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1000.00"),
        description="Wpłata klienta",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200
    assert "1 000,00 zł" in response.text

def test_accounting_report_ui_displays_totals(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2032, 10, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1080.00"),
        description="Wpłata klienta",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200
    assert "1 080,00 zł" in response.text
    assert "1 000,00 zł" in response.text
    assert "80,00 zł" in response.text


def test_accounting_report_ui_displays_booking_reservation(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,
        check_in=date(2032, 10, 10),
        check_out=date(2032, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200
    assert "1 150,00 zł" in response.text

def test_accounting_report_ui_displays_direct_and_booking(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
    created_reservation_cleanup,
):
    bank_repository = BankTransactionRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)

    transaction_id = bank_repository.create(
        transaction_date=date(2032, 10, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1080.00"),
        description="Wpłata Direct",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    reservation_id = reservation_repository.create(
        cottage_id=2,
        source_id=2,
        check_in=date(2032, 10, 15),
        check_out=date(2032, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200
    assert "1 080,00 zł" in response.text
    assert "1 150,00 zł" in response.text

def test_accounting_report_ui_displays_table_headers(
    api_client,
):
    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200

    assert "Data" in response.text
    assert "Źródło" in response.text
    assert "Kwota brutto" in response.text
    assert "Netto" in response.text
    assert "VAT" in response.text
    assert "Uwagi" in response.text

def test_accounting_report_calculates_direct_row_net_and_vat(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2032, 10, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1080.00"),
        description="Wpłata klienta",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2032, 10, 1),
        end_date=date(2032, 11, 1),
    )

    transaction = report["transactions"][0]

    assert transaction["gross_amount"] == Decimal("1080.00")
    assert transaction["net_amount"] == Decimal("1000.00")
    assert transaction["vat_amount"] == Decimal("80.00")

def test_accounting_report_calculates_booking_row_net_and_vat(
    db_connection,
    api_client,
    created_reservation_cleanup,
):
    repository = ReservationRepository(db_connection)

    reservation_id = repository.create(
        cottage_id=1,
        source_id=2,
        check_in=date(2032, 10, 10),
        check_out=date(2032, 10, 12),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2032, 10, 1),
        end_date=date(2032, 11, 1),
    )

    booking = report["booking_reservations"][0]

    assert booking["gross_amount"] == Decimal("1150.00")
    assert booking["net_amount"] == Decimal("1064.81")
    assert booking["vat_amount"] == Decimal("85.19")

def test_accounting_report_totals_sum_row_values(
    db_connection,
    created_bank_transaction_cleanup,
    created_reservation_cleanup,
):
    bank_repository = BankTransactionRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)

    transaction_id = bank_repository.create(
        transaction_date=date(2032, 10, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1080.00"),
        description="Wpłata Direct",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    reservation_id = reservation_repository.create(
        cottage_id=2,
        source_id=2,
        check_in=date(2032, 10, 15),
        check_out=date(2032, 10, 17),
        guests_count=2,
        status="CONFIRMED",
        total_amount=Decimal("1000.00"),
        commission_amount=Decimal("150.00"),
        accounting_included=True,
    )

    created_reservation_cleanup["reservation_ids"].append(
        reservation_id
    )

    report = generate_accounting_report(
        connection=db_connection,
        start_date=date(2032, 10, 1),
        end_date=date(2032, 11, 1),
    )

    assert report["total_gross"] == Decimal("2230.00")
    assert report["total_net"] == Decimal("2064.81")
    assert report["total_vat"] == Decimal("165.19")

def test_accounting_report_ui_displays_direct_net_and_vat(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2032, 10, 10),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1080.00"),
        description="Wpłata Direct",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 10,
            "year": 2032,
        },
    )

    assert response.status_code == 200
    assert "1 080,00 zł" in response.text
    assert "1 000,00 zł" in response.text
    assert "80,00 zł" in response.text

def test_accounting_report_ui_displays_month_and_summary(
    api_client,
):
    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "month": 7,
            "year": 2026,
        },
    )

    assert response.status_code == 200

    assert "Lipiec 2026" in response.text
    assert "Suma lipca" in response.text
    assert "Z przeniesienia" in response.text
    assert "RAZEM" in response.text
    assert "Strona 1 z 1" in response.text

def test_accounting_report_ui_displays_multiple_months(
    api_client,
):
    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "start_month": 6,
            "start_year": 2026,
            "end_month": 8,
            "end_year": 2026,
        },
    )

    assert response.status_code == 200

    assert "Czerwiec 2026" in response.text
    assert "Lipiec 2026" in response.text
    assert "Sierpień 2026" in response.text

    assert "Strona 1 z 3" in response.text
    assert "Strona 2 z 3" in response.text
    assert "Strona 3 z 3" in response.text
    assert 'name="start_month"' in response.text
    assert 'name="start_year"' in response.text
    assert 'name="end_month"' in response.text
    assert 'name="end_year"' in response.text
    assert 'id="start_month"' in response.text
    assert 'value="6" selected' in response.text
    assert 'value="8" selected' in response.text


def test_accounting_report_ui_displays_full_year(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    transaction_id = BankTransactionRepository(db_connection).create(
        transaction_date=date(2093, 12, 15),
        source_id=1,
        cottage_id=1,
        amount=Decimal("1080.00"),
        description="TEST-ACCOUNTING-FULL-YEAR-2093",
    )
    created_bank_transaction_cleanup.append(transaction_id)
    db_connection.commit()

    response = api_client.get(
        "/ui/reports/accounting",
        params={"month": 0, "year": 2093},
    )

    assert response.status_code == 200
    assert "Ewidencja sprzedaży — Styczeń 2093" in response.text
    assert "Ewidencja sprzedaży — Grudzień 2093" in response.text
    assert "Strona 12 z 12" in response.text
    assert "1 080,00 zł" in response.text
    assert 'value="0" selected' in response.text


def test_accounting_report_ui_displays_selected_month_totals(
    db_connection,
    api_client,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)
    transaction_ids = [
        repository.create(
            transaction_date=date(2094, 7, 10),
            source_id=1,
            cottage_id=1,
            amount=Decimal("1080.00"),
            description="TEST-ACCOUNTING-JULY-2094",
        ),
        repository.create(
            transaction_date=date(2094, 8, 10),
            source_id=1,
            cottage_id=1,
            amount=Decimal("850.00"),
            description="TEST-ACCOUNTING-AUGUST-2094",
        ),
    ]
    created_bank_transaction_cleanup.extend(transaction_ids)
    db_connection.commit()

    response = api_client.get(
        "/ui/reports/accounting",
        params={"month": 7, "year": 2094},
    )

    assert response.status_code == 200
    assert "Lipiec 2094" in response.text
    assert "Sierpień 2094" not in response.text
    assert "Suma lipca — brutto" in response.text
    assert "1 080,00 zł" in response.text
    assert "Netto" in response.text
    assert "1 000,00 zł" in response.text
    assert "VAT" in response.text
    assert "80,00 zł" in response.text
    assert 'value="7" selected' in response.text
    assert 'value="2094" selected' in response.text


def test_accounting_report_ui_preserves_year_only_link_and_default_month(
    api_client,
):
    response = api_client.get(
        "/ui/reports/accounting",
        params={"year": 2026},
    )

    assert response.status_code == 200
    assert "Ewidencja sprzedaży — Lipiec 2026" in response.text
    assert 'value="7" selected' in response.text
    assert 'value="2026" selected' in response.text


def test_accounting_report_ui_rejects_invalid_month(api_client):
    response = api_client.get(
        "/ui/reports/accounting",
        params={"month": 13, "year": 2026},
    )

    assert response.status_code == 400


def test_accounting_report_ui_renders_empty_reversed_custom_range(api_client):
    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "start_month": 10,
            "start_year": 2026,
            "end_month": 6,
            "end_year": 2026,
        },
    )

    assert response.status_code == 200
    assert "report-page" not in response.text
    assert "Brak danych dla wybranego zakresu" in response.text
    assert "Zakres niestandardowy" in response.text
    assert 'value="10" selected' in response.text
    assert 'value="6" selected' in response.text
    assert 'value="2026" selected' in response.text


@pytest.mark.parametrize(
    ("start_month", "end_month"),
    [(0, 8), (13, 8), (6, 0), (6, 13)],
)
def test_accounting_report_ui_rejects_invalid_custom_range_months(
    api_client,
    start_month,
    end_month,
):
    response = api_client.get(
        "/ui/reports/accounting",
        params={
            "start_month": start_month,
            "start_year": 2026,
            "end_month": end_month,
            "end_year": 2026,
        },
    )

    assert response.status_code == 400


def test_accounting_report_ui_uses_main_navigation_and_cashflow_layout(
    api_client,
):
    response = api_client.get(
        "/ui/reports/accounting",
        params={"month": 7, "year": 2026},
    )

    assert response.status_code == 200
    assert 'href="/ui/reports/accounting"' in response.text
    assert "Raport księgowy" in response.text
    assert "report-container" in response.text
    assert 'class="report-summary-card"' in response.text
    assert 'class="report-table"' in response.text
