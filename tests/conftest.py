import pytest
import inspect

from app.database import get_test_connection
from app.repositories.reservation_repository import ReservationRepository


def _apply_test_data_default(kwargs, is_test_data_explicit):
    if not is_test_data_explicit:
        kwargs["is_test_data"] = True
    return kwargs


def pytest_addoption(parser):
    parser.addoption(
        "--run-db-tests",
        action="store_true",
        default=False,
        help="run tests that require the dedicated MariaDB test database",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "db: requires the dedicated MariaDB test database",
    )


def pytest_report_header(config):
    if not config.getoption("--run-db-tests"):
        return "Database-dependent tests are deselected; pass --run-db-tests to request them."


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-db-tests"):
        return

    selected_items = []
    deselected_items = []
    for item in items:
        if "db" in item.keywords or "db_connection" in item.fixturenames:
            deselected_items.append(item)
        else:
            selected_items.append(item)

    if deselected_items:
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


@pytest.fixture
def mark_repository_created_reservations_as_test_data(monkeypatch):
    original_create = ReservationRepository.create
    sig = inspect.signature(original_create)

    def create_test_reservation(repository, *args, **kwargs):
        bound_args = sig.bind(repository, *args, **kwargs)
        is_test_data_explicit = "is_test_data" in bound_args.arguments
        bound_args.apply_defaults()
        _apply_test_data_default(kwargs, is_test_data_explicit)

        return original_create(repository, *args, **kwargs)

    monkeypatch.setattr(
        ReservationRepository,
        "create",
        create_test_reservation,
    )

@pytest.fixture
def db_connection(monkeypatch, mark_repository_created_reservations_as_test_data):
    from app import main

    monkeypatch.setattr(main, "get_connection", get_test_connection)
    connection = get_test_connection()

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


@pytest.fixture
def created_web_inquiry_cleanup(db_connection):
    inquiry_ids = []
    yield inquiry_ids

    with db_connection.cursor() as cursor:
        for inquiry_id in inquiry_ids:
            cursor.execute(
                "DELETE FROM web_inquiries WHERE id = %s",
                (inquiry_id,),
            )
    db_connection.commit()
