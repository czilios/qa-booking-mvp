from datetime import date
from decimal import Decimal

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)
from app.bank_transaction_service import (
    list_bank_transactions,
    sum_bank_transactions,
    create_bank_transaction,
)


def test_list_bank_transactions_by_date_range(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    july_id = repository.create(
        transaction_date=date(2026, 7, 31),
        source_id=1,
        cottage_id=2,
        amount=Decimal("500.00"),
    )

    august_id = repository.create(
        transaction_date=date(2026, 8, 1),
        source_id=1,
        cottage_id=2,
        amount=Decimal("1000.00"),
    )

    created_bank_transaction_cleanup.extend(
        [july_id, august_id]
    )

    db_connection.commit()

    transactions = list_bank_transactions(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    transaction_ids = [
        transaction["id"]
        for transaction in transactions
    ]

    assert transaction_ids == [july_id]

def test_sum_bank_transactions_by_date_range(
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    july_1_id = repository.create(
        transaction_date=date(2026, 7, 1),
        source_id=1,
        cottage_id=2,
        amount=Decimal("100.00"),
    )

    july_2_id = repository.create(
        transaction_date=date(2026, 7, 10),
        source_id=1,
        cottage_id=2,
        amount=Decimal("500.00"),
    )

    july_3_id = repository.create(
        transaction_date=date(2026, 7, 20),
        source_id=2,
        cottage_id=None,
        amount=Decimal("600.00"),
    )

    august_id = repository.create(
        transaction_date=date(2026, 8, 1),
        source_id=2,
        cottage_id=None,
        amount=Decimal("1000.00"),
    )

    created_bank_transaction_cleanup.extend(
        [
            july_1_id,
            july_2_id,
            july_3_id,
            august_id,
        ]
    )

    db_connection.commit()

    total = sum_bank_transactions(
        connection=db_connection,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 1),
    )

    assert Decimal(str(total)) == Decimal("1200.00")

def test_create_bank_transaction_service(
    db_connection,
    created_bank_transaction_cleanup,
):
    transaction_id = create_bank_transaction(
        connection=db_connection,
        transaction_date=date(2026, 8, 28),
        source_id=1,
        cottage_id=3,
        amount=Decimal("800.00"),
        description="Przelew Direct",
        notes="testing",
    )

    created_bank_transaction_cleanup.append(transaction_id)

    db_connection.commit()

    repository = BankTransactionRepository(db_connection)

    transaction = repository.get_by_id(transaction_id)

    assert transaction["source_id"] == 1
    assert transaction["cottage_id"] == 3
    assert Decimal(str(transaction["amount"])) == Decimal("800.00")
    assert transaction["description"] == "Przelew Direct"
    assert transaction["notes"] == "testing"