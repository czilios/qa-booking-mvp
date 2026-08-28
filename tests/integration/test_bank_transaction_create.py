from datetime import date
from decimal import Decimal
import pytest
from pymysql.err import IntegrityError

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)


def test_create_bank_transaction(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2026, 8, 24),
        source_id=1,
        cottage_id=3,
        amount=Decimal("800.00"),
        description="Domek 3",
        notes="testing",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    transaction = repository.get_by_id(transaction_id)

    assert transaction["transaction_date"] == date(2026, 8, 24)
    assert transaction["source_id"] == 1
    assert transaction["cottage_id"] == 3
    assert Decimal(str(transaction["amount"])) == Decimal("800.00")
    assert transaction["description"] == "Domek 3"
    assert transaction["notes"] == "testing"

def test_create_bank_transaction_without_cottage(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2026, 8, 20),
        source_id=2,
        cottage_id=None,
        amount=Decimal("5245.36"),
        description="BOOKING.COM",
        notes="testing",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    transaction = repository.get_by_id(transaction_id)

    assert transaction["source_id"] == 2
    assert transaction["cottage_id"] is None
    assert Decimal(str(transaction["amount"])) == Decimal("5245.36")
    assert transaction["description"] == "BOOKING.COM"
    assert transaction["notes"] == "testing"

def test_create_bank_transaction_preserves_decimal_amount(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    transaction_id = repository.create(
        transaction_date=date(2026, 8, 27),
        source_id=2,
        cottage_id=None,
        amount=Decimal("2427.05"),
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    transaction = repository.get_by_id(transaction_id)

    assert Decimal(str(transaction["amount"])) == Decimal("2427.05")

def test_create_bank_transaction_rejects_zero_amount(
    db_connection,
):
    repository = BankTransactionRepository(db_connection)

    with pytest.raises(ValueError):
        repository.create(
            transaction_date=date(2026, 8, 27),
            source_id=2,
            cottage_id=None,
            amount=Decimal("0.00"),
        )

def test_create_bank_transaction_rejects_negative_amount(
    db_connection,
):
    repository = BankTransactionRepository(db_connection)

    with pytest.raises(ValueError):
        repository.create(
            transaction_date=date(2026, 8, 27),
            source_id=2,
            cottage_id=None,
            amount=Decimal("-500.00"),
        )

def test_create_bank_transaction_rejects_unknown_source(
    db_connection,
):
    repository = BankTransactionRepository(db_connection)

    with pytest.raises(IntegrityError):
        repository.create(
            transaction_date=date(2026, 8, 27),
            source_id=999,
            cottage_id=None,
            amount=Decimal("500.00"),
        )

def test_create_multiple_bank_transactions(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    first_id = repository.create(
        transaction_date=date(2026, 8, 27),
        source_id=1,
        cottage_id=2,
        amount=Decimal("500.00"),
    )

    second_id = repository.create(
        transaction_date=date(2026, 8, 27),
        source_id=1,
        cottage_id=3,
        amount=Decimal("800.00"),
    )

    third_id = repository.create(
        transaction_date=date(2026, 8, 27),
        source_id=1,
        cottage_id=2,
        amount=Decimal("700.00"),
    )

    created_bank_transaction_cleanup.extend(
        [first_id, second_id, third_id]
    )

    db_connection.commit()

    assert first_id != second_id
    assert second_id != third_id

def test_list_bank_transactions_by_date_range(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    july_transaction_id = repository.create(
        transaction_date=date(2026, 7, 31),
        source_id=1,
        cottage_id=2,
        amount=Decimal("500.00"),
    )

    august_transaction_id = repository.create(
        transaction_date=date(2026, 8, 1),
        source_id=1,
        cottage_id=2,
        amount=Decimal("1000.00"),
    )

    june_transaction_id = repository.create(
        transaction_date=date(2026, 6, 30),
        source_id=1,
        cottage_id=2,
        amount=Decimal("300.00"),
    )

    created_bank_transaction_cleanup.extend(
        [
            july_transaction_id,
            august_transaction_id,
            june_transaction_id,
        ]
    )

    db_connection.commit()

    transactions = repository.list_by_date_range(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    transaction_ids = [
        transaction["id"]
        for transaction in transactions
    ]

    assert july_transaction_id in transaction_ids
    assert august_transaction_id not in transaction_ids
    assert june_transaction_id not in transaction_ids

def test_sum_bank_transactions_by_date_range(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    july_transaction_ids = [
        repository.create(
            transaction_date=date(2026, 7, 1),
            source_id=1,
            cottage_id=2,
            amount=Decimal("100.00"),
        ),
        repository.create(
            transaction_date=date(2026, 7, 10),
            source_id=1,
            cottage_id=2,
            amount=Decimal("500.00"),
        ),
        repository.create(
            transaction_date=date(2026, 7, 20),
            source_id=2,
            cottage_id=None,
            amount=Decimal("600.00"),
        ),
        repository.create(
            transaction_date=date(2026, 7, 31),
            source_id=2,
            cottage_id=None,
            amount=Decimal("800.00"),
        ),
    ]

    august_transaction_id = repository.create(
        transaction_date=date(2026, 8, 1),
        source_id=2,
        cottage_id=None,
        amount=Decimal("1000.00"),
    )

    created_bank_transaction_cleanup.extend(
        july_transaction_ids + [august_transaction_id]
    )

    db_connection.commit()

    total = repository.sum_by_date_range(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    assert Decimal(str(total)) == Decimal("2000.00")

def test_sum_bank_transactions_returns_zero_for_empty_range(
    db_connection,
):
    repository = BankTransactionRepository(db_connection)

    total = repository.sum_by_date_range(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
    )

    assert Decimal(str(total)) == Decimal("0.00")

def test_sum_bank_transactions_returns_zero_for_empty_range(
    db_connection,
):
    repository = BankTransactionRepository(db_connection)

    total = repository.sum_by_date_range(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 6, 1),
    )

    assert Decimal(str(total)) == Decimal("0.00")

def test_sum_bank_transactions_by_source_and_date_range(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    booking_july_id = repository.create(
        transaction_date=date(2026, 7, 31),
        source_id=2,
        cottage_id=None,
        amount=Decimal("700.00"),
    )

    booking_august_1_id = repository.create(
        transaction_date=date(2026, 8, 5),
        source_id=2,
        cottage_id=None,
        amount=Decimal("5245.36"),
    )

    booking_august_2_id = repository.create(
        transaction_date=date(2026, 8, 20),
        source_id=2,
        cottage_id=None,
        amount=Decimal("2427.05"),
    )

    direct_august_id = repository.create(
        transaction_date=date(2026, 8, 10),
        source_id=1,
        cottage_id=3,
        amount=Decimal("1000.00"),
    )

    created_bank_transaction_cleanup.extend(
        [
            booking_july_id,
            booking_august_1_id,
            booking_august_2_id,
            direct_august_id,
        ]
    )

    db_connection.commit()

    total = repository.sum_by_source_and_date_range(
        source_id=2,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 9, 1),
    )

    assert Decimal(str(total)) == Decimal("7672.41")

def test_sum_bank_transactions_by_cottage_and_date_range(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    cottage_2_july_id = repository.create(
        transaction_date=date(2026, 7, 10),
        source_id=1,
        cottage_id=2,
        amount=Decimal("500.00"),
    )

    cottage_2_august_id = repository.create(
        transaction_date=date(2026, 8, 5),
        source_id=1,
        cottage_id=2,
        amount=Decimal("1250.00"),
    )

    cottage_3_august_id = repository.create(
        transaction_date=date(2026, 8, 10),
        source_id=1,
        cottage_id=3,
        amount=Decimal("900.00"),
    )

    booking_without_cottage_id = repository.create(
        transaction_date=date(2026, 8, 15),
        source_id=2,
        cottage_id=None,
        amount=Decimal("5000.00"),
    )

    created_bank_transaction_cleanup.extend(
        [
            cottage_2_july_id,
            cottage_2_august_id,
            cottage_3_august_id,
            booking_without_cottage_id,
        ]
    )

    db_connection.commit()

    total = repository.sum_by_cottage_and_date_range(
        cottage_id=2,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 9, 1),
    )

    assert Decimal(str(total)) == Decimal("1250.00")

def test_list_bank_transactions_orders_by_date_and_id(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    first_id = repository.create(
        transaction_date=date(2026, 8, 10),
        source_id=1,
        cottage_id=2,
        amount=Decimal("100.00"),
    )

    second_id = repository.create(
        transaction_date=date(2026, 8, 10),
        source_id=1,
        cottage_id=2,
        amount=Decimal("200.00"),
    )

    third_id = repository.create(
        transaction_date=date(2026, 8, 5),
        source_id=1,
        cottage_id=2,
        amount=Decimal("300.00"),
    )

    created_bank_transaction_cleanup.extend(
        [first_id, second_id, third_id]
    )

    db_connection.commit()

    transactions = repository.list_by_date_range(
        start_date=date(2026, 8, 1),
        end_date=date(2026, 9, 1),
    )

    transaction_ids = [
        transaction["id"]
        for transaction in transactions
    ]

    assert transaction_ids == [
        third_id,
        first_id,
        second_id,
    ]