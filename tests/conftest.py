import pytest
import inspect

from app.database import get_connection
from app.repositories.reservation_repository import ReservationRepository


@pytest.fixture(autouse=True)
def mark_repository_created_reservations_as_test_data(monkeypatch):
    original_create = ReservationRepository.create
    sig = inspect.signature(original_create)

    def create_test_reservation(repository, *args, **kwargs):
        # Bindujemy przekazane argumenty do sygnatury metody create
        bound_args = sig.bind(repository, *args, **kwargs)
        bound_args.apply_defaults()
        
        # Jeśli is_test_data nie zostało jawnie przekazane (lub ma wartość domyślną z metody, np. False)
        # i chcemy wymusić w testach True:
        if bound_args.arguments.get('is_test_data') is not False:
            kwargs['is_test_data'] = True
        else:
            kwargs['is_test_data'] = False

        return original_create(repository, *args, **kwargs)

    monkeypatch.setattr(
        ReservationRepository,
        "create",
        create_test_reservation,
    )

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
