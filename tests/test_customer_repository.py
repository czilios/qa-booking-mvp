from app.repositories.customer_repository import CustomerRepository

def test_get_customer_by_phone(db_connection):
    repository = CustomerRepository(db_connection)

    customer_id = repository.create(
        first_name=None,
        last_name=None,
        phone="791443376",
        email=None,
    )

    customer = repository.get_by_phone("791443376")

    assert customer is not None
    assert customer["id"] == customer_id
    assert customer["phone"] == "791443376"