import pytest 

from app.customer_service import create_customer

from app.repositories.customer_repository import CustomerRepository


def test_create_customer_creates_customer(db_connection):
    repository = CustomerRepository(db_connection)

    customer_id = repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
        email="jan@example.com",
    )

    assert customer_id is not None

    customer = repository.get_by_id(customer_id)

    assert customer["first_name"] == "Jan"
    assert customer["last_name"] == "Kowalski"
    assert customer["phone"] == "+48666777567"
    assert customer["email"] == "jan@example.com"

def test_create_customer_without_email(db_connection):
    repository = CustomerRepository(db_connection)

    customer_id = repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
    )

    customer = repository.get_by_id(customer_id)

    assert customer["first_name"] == "Jan"
    assert customer["last_name"] == "Kowalski"
    assert customer["phone"] == "+48666777567"
    assert customer["email"] is None

def test_create_customer_accepts_german_phone_number(db_connection):
    repository = CustomerRepository(db_connection)

    customer_id = repository.create(
        first_name="Hans",
        last_name="Müller",
        phone="+491701234567",
        email="hans@example.de",
    )

    customer = repository.get_by_id(customer_id)

    assert customer["phone"] == "+491701234567"
    assert customer["email"] == "hans@example.de"

def test_create_customer_rejects_empty_first_name(db_connection):
    with pytest.raises(ValueError, match="First name is required"):
        create_customer(
            connection=db_connection,
            first_name="",
            last_name="Kowalski",
            phone="+48666777567",
            email="jan@example.com",
        )

def test_create_customer_rejects_empty_last_name(db_connection):
    with pytest.raises(ValueError, match="Last name is required"):
        create_customer(
            connection=db_connection,
            first_name="Jan",
            last_name="",
            phone="+48666777567",
            email="jan@example.com",
        )

def test_create_customer_rejects_empty_phone(db_connection):
    with pytest.raises(ValueError, match="Phone is required"):
        create_customer(
            connection=db_connection,
            first_name="Jan",
            last_name="Kowalski",
            phone="",
            email="jan@example.com",
        )

def test_create_customer_rejects_whitespace_only_first_name(db_connection):
    with pytest.raises(ValueError, match="First name is required"):
        create_customer(
            connection=db_connection,
            first_name="   ",
            last_name="Kowalski",
            phone="+48666777567",
            email="jan@example.com",
        )

def test_create_customer_normalizes_phone_format(db_connection):
    customer_id = create_customer(
        connection=db_connection,
        first_name="Jan",
        last_name="Kowalski",
        phone="791-443-376",
        email="jan@example.com",
    )

    repository = CustomerRepository(db_connection)

    customer = repository.get_by_id(customer_id)

    assert customer["phone"] == "791443376"