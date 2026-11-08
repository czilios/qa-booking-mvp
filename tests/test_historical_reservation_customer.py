from unittest.mock import Mock

from fastapi.testclient import TestClient

from app import main


def _client(monkeypatch, connection):
    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_db_connection,
        lambda: connection,
    )
    return TestClient(main.app, raise_server_exceptions=False)


def _reservation_data(**overrides):
    return {
        "cottage_id": "1",
        "source_id": "1",
        "check_in": "2026-07-10",
        "check_out": "2026-07-17",
        "guests_count": "2",
        "total_amount": "2100.00",
        **overrides,
    }


def test_historical_reservation_reuses_customer_by_normalized_phone(monkeypatch):
    connection = Mock()
    customer_repository = Mock()
    customer_repository.get_by_phone.return_value = {"id": 17}
    create_reservation = Mock(return_value=42)
    monkeypatch.setattr(main, "CustomerRepository", lambda _: customer_repository)
    monkeypatch.setattr(main, "create_historical_reservation", create_reservation)

    response = _client(monkeypatch, connection).post(
        "/ui/reservations/historical",
        data=_reservation_data(phone="+48 600-000-000"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    customer_repository.get_by_phone.assert_called_once_with("+48600000000")
    create_reservation.assert_called_once()
    assert create_reservation.call_args.kwargs["customer_id"] == 17
    connection.commit.assert_called_once()


def test_historical_reservation_creates_named_customer_for_new_phone(monkeypatch):
    connection = Mock()
    customer_repository = Mock()
    customer_repository.get_by_phone.return_value = None
    customer_writer = Mock()
    customer_writer.create.return_value = 23
    create_reservation = Mock(return_value=43)
    monkeypatch.setattr(main, "CustomerRepository", lambda _: customer_repository)
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda _: customer_writer)
    monkeypatch.setattr(main, "create_historical_reservation", create_reservation)

    response = _client(monkeypatch, connection).post(
        "/ui/reservations/historical",
        data=_reservation_data(
            phone="+48 600-000-000",
            first_name="Jan",
            last_name="Kowalski",
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303
    customer_writer.create.assert_called_once_with(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48600000000",
        email=None,
    )
    assert create_reservation.call_args.kwargs["customer_id"] == 23
    connection.commit.assert_called_once()


def test_historical_reservation_rejects_new_customer_without_both_names(monkeypatch):
    connection = Mock()
    customer_repository = Mock()
    customer_repository.get_by_phone.return_value = None
    customer_writer = Mock()
    create_reservation = Mock(return_value=44)
    monkeypatch.setattr(main, "CustomerRepository", lambda _: customer_repository)
    monkeypatch.setattr("app.customer_service.CustomerRepository", lambda _: customer_writer)
    monkeypatch.setattr(main, "create_historical_reservation", create_reservation)

    response = _client(monkeypatch, connection).post(
        "/ui/reservations/historical",
        data=_reservation_data(phone="+48600000000", first_name="Jan"),
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Last name is required"
    customer_writer.create.assert_not_called()
    create_reservation.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()