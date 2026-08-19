from decimal import Decimal

from app.repositories.customer_repository import CustomerRepository



def test_create_customer_returns_201(api_client, db_connection):
    response = api_client.post(
        "/api/customers",
        json={
            "first_name": "Jan",
            "last_name": "Kowalski",
            "phone": "+48666777567",
            "email": "jan@example.com",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["first_name"] == "Jan"
    assert data["last_name"] == "Kowalski"
    assert data["phone"] == "+48666777567"
    assert data["email"] == "jan@example.com"

def test_create_customer_normalizes_phone(api_client):
    response = api_client.post(
        "/api/customers",
        json={
            "first_name": "Jan",
            "last_name": "Kowalski",
            "phone": "791-443-376",
            "email": "jan@example.com",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["phone"] == "791443376"

def test_get_customer_returns_200(api_client, db_connection):
    repository = CustomerRepository(db_connection)

    customer_id = repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
        email="jan@example.com",
    )

    response = api_client.get(
        f"/api/customers/{customer_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == customer_id
    assert data["first_name"] == "Jan"
    assert data["last_name"] == "Kowalski"
    assert data["phone"] == "+48666777567"
    assert data["email"] == "jan@example.com"

def test_get_customer_returns_404_for_nonexistent_customer(api_client):
    response = api_client.get(
        "/api/customers/999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"

def test_update_customer_returns_200(api_client, db_connection):
    repository = CustomerRepository(db_connection)

    customer_id = repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="791443376",
        email="old@example.com",
    )

    response = api_client.put(
        f"/api/customers/{customer_id}",
        json={
            "first_name": "Jan",
            "last_name": "Kowalski",
            "phone": "791-555-444",
            "email": "new@example.com",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == customer_id
    assert data["phone"] == "791555444"
    assert data["email"] == "new@example.com"

