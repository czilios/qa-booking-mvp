from datetime import date
from decimal import Decimal

from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository


def test_create_payment_returns_201(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    response = api_client.post(
        "/api/payments",
        json={
            "reservation_id": reservation_id,
            "payment_type": "DEPOSIT",
            "amount": "500.00",
        },
    )

    assert response.status_code == 201

    payment_repository = PaymentRepository(db_connection)
    payment = payment_repository.get_payment_by_id(
        response.json()
    )

    assert payment["reservation_id"] == reservation_id
    assert payment["type"] == "DEPOSIT"
    assert payment["amount"] == Decimal("500.00")
    assert payment["status"] == "UNPAID"

def test_create_payment_returns_404_for_nonexistent_reservation(
    db_connection,
    api_client,
):
    response = api_client.post(
        "/api/payments",
        json={
            "reservation_id": 999999,
            "payment_type": "DEPOSIT",
            "amount": "500.00",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"

def test_create_payment_returns_409_for_invalid_payment_type(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    response = api_client.post(
        "/api/payments",
        json={
            "reservation_id": reservation_id,
            "payment_type": "INVALID",
            "amount": "500.00",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Invalid payment type"

def test_create_payment_returns_409_for_zero_amount(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    response = api_client.post(
        "/api/payments",
        json={
            "reservation_id": reservation_id,
            "payment_type": "DEPOSIT",
            "amount": "0.00",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Payment amount must be greater than zero"
    )

def test_create_payment_returns_409_for_negative_amount(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 10, 10),
        check_out=date(2027, 10, 17),
        guests_count=2,
    )

    response = api_client.post(
        "/api/payments",
        json={
            "reservation_id": reservation_id,
            "payment_type": "DEPOSIT",
            "amount": "-500.00",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Payment amount must be greater than zero"
    )

