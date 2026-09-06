from datetime import date
from decimal import Decimal
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
    assert "1000.00" in response.text

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
    assert "1080.00" in response.text
    assert "1000.00" in response.text
    assert "80.00" in response.text


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
    assert "1150.00" in response.text

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
    assert "1080.00" in response.text
    assert "1150.00" in response.text

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
    assert "1080.00" in response.text
    assert "1000.00" in response.text
    assert "80.00" in response.text

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
