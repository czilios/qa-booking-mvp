from datetime import date, datetime
from decimal import Decimal

from app.accounting_report_service import AccountingReportService
from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository

def test_accounting_report_june_and_july_and_august(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    june_transactions = [
        (date(2026, 6, 19), 1, Decimal("400.00")),
        (date(2026, 6, 19), 1, Decimal("900.00")),
        (date(2026, 6, 25), 1, Decimal("500.00")),
        (date(2026, 6, 26), 1, Decimal("500.00")),
    ]

    july_transactions = [
        (date(2026, 7, 1), 1, Decimal("1450.00")),
        (date(2026, 7, 5), 1, Decimal("1425.00")),
        (date(2026, 7, 10), 1, Decimal("300.00")),
        (date(2026, 7, 13), 1, Decimal("500.00")),
        (date(2026, 7, 13), 1, Decimal("840.00")),
        (date(2026, 7, 16), 1, Decimal("850.50")),
        (date(2026, 7, 23), 1, Decimal("834.30")),
        (date(2026, 7, 23), 1, Decimal("450.00")),
        (date(2026, 7, 30), 1, Decimal("810.00")),
        (date(2026, 7, 30), 1, Decimal("1636.74")),
    
    ]
    august_transactions = [
    (date(2026, 8, 6), 1, Decimal("1080.00")),
    (date(2026, 8, 6), 1, Decimal("1134.00")),
    (date(2026, 8, 13), 1, Decimal("900.00")),
    ]

    created_ids = []

    for transaction_date, source_id, amount in (
        june_transactions + july_transactions + august_transactions
    ):
        transaction_id = repository.create(
            transaction_date=transaction_date,
            source_id=source_id,
            cottage_id=None,
            amount=amount,
        )

        created_ids.append(transaction_id)

    created_bank_transaction_cleanup.extend(created_ids)

    db_connection.commit()

def test_accounting_report_calculates_net_and_vat(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2026, 8, 15),
        source_id=1,
        cottage_id=2,
        amount=Decimal("1080.00"),
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    accounting_report_service = AccountingReportService(
        payment_repository=None,
    )

    report = accounting_report_service.generate_accounting_report(
        bank_transaction_repository=repository,
        year=2026,
    )

    august = report["months"][7]

    assert august["monthly_gross"] == Decimal("1080.00")
    assert august["monthly_net"] == Decimal("1000.00")
    assert august["monthly_vat"] == Decimal("80.00")

def test_accounting_report_calculates_carry_over(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    june_id = repository.create(
        transaction_date=date(2026, 6, 19),
        source_id=1,
        cottage_id=None,
        amount=Decimal("2300.00"),
    )

    july_id = repository.create(
        transaction_date=date(2026, 7, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("9296.54"),
    )

    august_id = repository.create(
        transaction_date=date(2026, 8, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("2214.00"),
    )

    created_bank_transaction_cleanup.extend(
        [june_id, july_id, august_id]
    )

    db_connection.commit()

    accounting_report_service = AccountingReportService(
        payment_repository=None,
    )

    report = accounting_report_service.generate_accounting_report(
        bank_transaction_repository=repository,
        year=2026,
    )

    june = report["months"][5]
    july = report["months"][6]
    august = report["months"][7]

    assert june["carry_over_gross"] == Decimal("0.00")
    assert june["total_gross"] == Decimal("2300.00")

    assert july["carry_over_gross"] == Decimal("2300.00")
    assert july["total_gross"] == Decimal("11596.54")

    assert august["carry_over_gross"] == Decimal("11596.54")
    assert august["total_gross"] == Decimal("13810.54")

def test_accounting_report_calculates_carry_over_net_and_vat(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)
    june_id = repository.create(
    transaction_date=date(2026, 6, 19),
    source_id=1,
    cottage_id=None,
    amount=Decimal("1080.00"),
    )

    july_id = repository.create(
    transaction_date=date(2026, 7, 15),
    source_id=1,
    cottage_id=None,
    amount=Decimal("1080.00"),
    )

    august_id = repository.create(
    transaction_date=date(2026, 8, 15),
    source_id=1,
    cottage_id=None,
    amount=Decimal("1080.00"),
 )
    created_bank_transaction_cleanup.extend(
        [june_id, july_id, august_id]
    )

    db_connection.commit()

    accounting_report_service = AccountingReportService(
        payment_repository=None,
    )

    report = accounting_report_service.generate_accounting_report(
        bank_transaction_repository=repository,
        year=2026,
    )

    june = report["months"][5]
    july = report["months"][6]
    august = report["months"][7]

    # Czerwiec
    assert june["carry_over_net"] == Decimal("0.00")
    assert june["carry_over_vat"] == Decimal("0.00")

    # Lipiec - przenosimy czerwiec
    assert july["carry_over_net"] == Decimal("1000.00")
    assert july["carry_over_vat"] == Decimal("80.00")

    # Sierpień - przenosimy czerwiec + lipiec
    assert august["carry_over_net"] == Decimal("2000.00")
    assert august["carry_over_vat"] == Decimal("160.00")

def test_accounting_report_calculates_total_net_and_vat(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    june_id = repository.create(
        transaction_date=date(2026, 6, 19),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1080.00"),
    )

    july_id = repository.create(
        transaction_date=date(2026, 7, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1080.00"),
    )

    august_id = repository.create(
        transaction_date=date(2026, 8, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1080.00"),
    )

    created_bank_transaction_cleanup.extend(
        [june_id, july_id, august_id]
    )

    db_connection.commit()

    accounting_report_service = AccountingReportService(
        payment_repository=None,
    )

    report = accounting_report_service.generate_accounting_report(
        bank_transaction_repository=repository,
        year=2026,
    )

    june = report["months"][5]
    july = report["months"][6]
    august = report["months"][7]

    assert june["total_net"] == Decimal("1000.00")
    assert june["total_vat"] == Decimal("80.00")

    assert july["total_net"] == Decimal("2000.00")
    assert july["total_vat"] == Decimal("160.00")

    assert august["total_net"] == Decimal("3000.00")
    assert august["total_vat"] == Decimal("240.00")

def test_accounting_report_calculates_final_totals(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    june_id = repository.create(
        transaction_date=date(2026, 6, 19),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1080.00"),
    )

    july_id = repository.create(
        transaction_date=date(2026, 7, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1080.00"),
    )

    august_id = repository.create(
        transaction_date=date(2026, 8, 15),
        source_id=1,
        cottage_id=None,
        amount=Decimal("1080.00"),
    )

    created_bank_transaction_cleanup.extend(
        [june_id, july_id, august_id]
    )

    db_connection.commit()

    accounting_report_service = AccountingReportService(
        payment_repository=None,
    )

    report = accounting_report_service.generate_accounting_report(
        bank_transaction_repository=repository,
        year=2026,
    )

    assert report["total_gross"] == Decimal("3240.00")
    assert report["total_net"] == Decimal("3000.00")
    assert report["total_vat"] == Decimal("240.00")



