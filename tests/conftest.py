import pytest

from app.database import get_connection


@pytest.fixture
def db_connection():
    connection = get_connection()

    try:
        connection.begin()
        yield connection
        connection.rollback()
    finally:
        connection.close()


@pytest.fixture
def created_reservation_cleanup(db_connection):
    created_reservation_ids = []
    created_customer_ids = []

    yield {
        "reservation_ids": created_reservation_ids,
        "customer_ids": created_customer_ids,
    }

    with db_connection.cursor() as cursor:

        for reservation_id in created_reservation_ids:
            cursor.execute(
                """
                DELETE FROM payments
                WHERE reservation_id = %s
                """,
                (reservation_id,),
            )

            cursor.execute(
                """
                DELETE FROM reservations
                WHERE id = %s
                """,
                (reservation_id,),
            )

        for customer_id in created_customer_ids:
            cursor.execute(
                """
                DELETE FROM customers
                WHERE id = %s
                """,
                (customer_id,),
            )

    db_connection.commit()

@pytest.fixture
def created_bank_transaction_cleanup(db_connection):
    created_bank_transaction_ids = []

    yield created_bank_transaction_ids

    with db_connection.cursor() as cursor:
        for transaction_id in created_bank_transaction_ids:
            cursor.execute(
                """
                DELETE FROM bank_transactions
                WHERE id = %s
                """,
                (transaction_id,),
            )

    db_connection.commit()