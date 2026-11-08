from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.customer_service import create_customer, update_customer


@pytest.mark.parametrize("contact", [{"phone": "123-456"}, {"email": "guest@example.com"}])
def test_create_customer_accepts_one_contact(monkeypatch, contact):
    repository = Mock()
    repository.create.return_value = 5
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda connection: repository)

    assert create_customer(Mock(), first_name="Jan", last_name="Kowalski", **contact) == 5
    assert repository.create.call_args.kwargs["phone"] == ("123456" if "phone" in contact else None)


@pytest.mark.parametrize("whitespace", ["", " ", "\t", "\r", "\n", " \t\r\n"])
def test_customer_rejects_empty_contacts_before_repository(monkeypatch, whitespace):
    repository = Mock()
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda connection: repository)
    with pytest.raises(ValueError, match="Phone or email is required"):
        create_customer(Mock(), first_name="Jan", last_name="Kowalski", phone=whitespace, email=whitespace)
    repository.create.assert_not_called()


@pytest.mark.parametrize("first_name,last_name", [(None, "Kowalski"), ("Jan", "\t\r\n")])
def test_customer_requires_first_and_last_name(first_name, last_name):
    with pytest.raises(ValueError, match="name is required"):
        create_customer(Mock(), first_name=first_name, last_name=last_name, email="guest@example.com")


def test_update_customer_accepts_email_only(monkeypatch):
    repository = Mock()
    repository.get_by_id.return_value = {"id": 5}
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda connection: repository)

    update_customer(Mock(), 5, first_name="Jan", last_name="Kowalski", email="guest@example.com")
    assert repository.update.call_args.kwargs["phone"] is None


@pytest.mark.parametrize("contact", [{"phone": "+48123456789"}, {"email": "guest@example.com"}])
def test_customer_api_accepts_one_contact(monkeypatch, contact):
    connection = Mock()
    repository = Mock()
    repository.create.return_value = 5
    repository.get_by_id.return_value = {"id": 5}
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda db: repository)
    monkeypatch.setattr(main, "CustomerRepository", lambda db: repository)

    response = TestClient(main.app).post(
        "/api/customers", json={"first_name": "Jan", "last_name": "Kowalski", **contact}
    )

    assert response.status_code == 201
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize("contact", [None, "", " \t\r\n"])
def test_customer_api_rejects_missing_or_whitespace_contacts(monkeypatch, contact):
    connection = Mock()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    response = TestClient(main.app).post(
        "/api/customers",
        json={"first_name": "Jan", "last_name": "Kowalski", "phone": contact, "email": contact},
    )
    assert response.status_code == 400
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()


@pytest.mark.parametrize("payload", [{"last_name": "Kowalski"}, {"first_name": "Jan"}, {"first_name": "\t", "last_name": "Kowalski"}])
def test_customer_api_rejects_missing_or_blank_names(monkeypatch, payload):
    connection = Mock()
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    response = TestClient(main.app).post("/api/customers", json={**payload, "email": "guest@example.com"})
    assert response.status_code in (400, 422)
    connection.commit.assert_not_called()


def test_customer_api_update_accepts_email_only(monkeypatch):
    connection = Mock()
    repository = Mock()
    repository.get_by_id.return_value = {"id": 5}
    monkeypatch.setattr(main, "get_connection", lambda: connection)
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda db: repository)

    response = TestClient(main.app).put(
        "/api/customers/5", json={"first_name": "Jan", "last_name": "Kowalski", "email": "guest@example.com"}
    )
    assert response.status_code == 200
    connection.commit.assert_called_once()