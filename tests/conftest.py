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
def created_reservation_cleanup():
    created_reservation_ids = []
    created_customer_ids = []

    yield {
        "reservation_ids": created_reservation_ids,
        "customer_ids": created_customer_ids,
    }

    connection = get_connection()

    try:
        with connection.cursor() as cursor:

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

        connection.commit()

    finally:
        connection.close()
        