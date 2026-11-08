from pymysql.connections import Connection

from app.repositories.customer_repository import CustomerRepository


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "").replace(".", "")


def validate_customer_details(
    first_name: str | None,
    last_name: str | None,
    phone: str | None,
    email: str | None,
) -> tuple[str, str, str | None, str | None]:
    if not first_name or not first_name.strip():
        raise ValueError("First name is required")
    if not last_name or not last_name.strip():
        raise ValueError("Last name is required")

    normalized_phone = normalize_phone(phone.strip()) if phone and phone.strip() else None
    normalized_email = email.strip() if email and email.strip() else None
    if not normalized_phone and not normalized_email:
        raise ValueError("Phone or email is required")

    return first_name.strip(), last_name.strip(), normalized_phone, normalized_email


def create_customer(
    connection: Connection,
    phone: str | None = None,
    first_name: str |None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> int:

    first_name, last_name, normalized_phone, email = validate_customer_details(
        first_name, last_name, phone, email
    )

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
    phone: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
):


    first_name, last_name, normalized_phone, email = validate_customer_details(
        first_name, last_name, phone, email
    )

    repository = CustomerRepository(connection)

    customer = repository.get_by_id(customer_id)

    if customer is None:
        raise ValueError("Customer not found")

    repository.update(
        customer_id=customer_id,
        first_name=first_name,
        last_name=last_name,
        phone=normalized_phone,
        email=email,
    )

    return repository.get_by_id(customer_id)
