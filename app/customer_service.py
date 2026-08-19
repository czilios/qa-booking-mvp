from pymysql.connections import Connection

from app.repositories.customer_repository import CustomerRepository


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "").replace(".", "")


def create_customer(
    connection: Connection,
    first_name: str,
    last_name: str,
    phone: str,
    email: str | None = None,
) -> int:
    if not first_name.strip():
        raise ValueError("First name is required")

    if not last_name.strip():
        raise ValueError("Last name is required")

    if not phone.strip():
        raise ValueError("Phone is required")

    normalized_phone = normalize_phone(phone)

    repository = CustomerRepository(connection)

    return repository.create(
        first_name=first_name,
        last_name=last_name,
        phone=normalized_phone,
        email=email,
    )

def get_customer(
    connection: Connection,
    customer_id: int,
):
    repository = CustomerRepository(connection)

    customer = repository.get_by_id(customer_id)

    if customer is None:
        raise ValueError("Customer not found")

    return customer
def update_customer(
    connection: Connection,
    customer_id: int,
    first_name: str,
    last_name: str,
    phone: str,
    email: str | None = None,
):
    if not first_name.strip():
        raise ValueError("First name is required")

    if not last_name.strip():
        raise ValueError("Last name is required")

    if not phone.strip():
        raise ValueError("Phone is required")

    repository = CustomerRepository(connection)

    customer = repository.get_by_id(customer_id)

    if customer is None:
        raise ValueError("Customer not found")

    normalized_phone = normalize_phone(phone)

    repository.update(
        customer_id=customer_id,
        first_name=first_name,
        last_name=last_name,
        phone=normalized_phone,
        email=email,
    )

    return repository.get_by_id(customer_id)
