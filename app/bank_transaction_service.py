from datetime import date
from decimal import Decimal

from pymysql.connections import Connection

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)


def list_bank_transactions(
    connection: Connection,
    start_date: date,
    end_date: date,
):
    repository = BankTransactionRepository(connection)

    return repository.list_by_date_range(
        start_date=start_date,
        end_date=end_date,
    )


def sum_bank_transactions(
    connection: Connection,
    start_date: date,
    end_date: date,
) -> Decimal:
    repository = BankTransactionRepository(connection)

    return repository.sum_by_date_range(
        start_date=start_date,
        end_date=end_date,
    )

def create_bank_transaction(
    connection: Connection,
    transaction_date: date,
    source_id: int,
    cottage_id: int | None,
    amount: Decimal,
    description: str | None = None,
    notes: str | None = None,
) -> int:
    repository = BankTransactionRepository(connection)

    return repository.create(
        transaction_date=transaction_date,
        source_id=source_id,
        cottage_id=cottage_id,
        amount=amount,
        description=description,
        notes=notes,
    )

