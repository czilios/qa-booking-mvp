from datetime import date, datetime
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

def test_get_payment_returns_200(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 11, 10),
        check_out=date(2027, 11, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    response = api_client.get(
        f"/api/payments/{payment_id}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == payment_id
    assert data["reservation_id"] == reservation_id
    assert data["type"] == "DEPOSIT"
    assert Decimal(data["amount"]) == Decimal("500.00")
    assert data["status"] == "UNPAID"
    assert data["paid_at"] is None

def test_get_payment_returns_404_for_nonexistent_payment(
    api_client,
):
    response = api_client.get(
        "/api/payments/999999",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"

def test_mark_payment_as_paid_returns_200(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 11, 10),
        check_out=date(2027, 11, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    paid_at = datetime(2027, 11, 1, 14, 30, 0)

    response = api_client.put(
        f"/api/payments/{payment_id}/paid",
        json={
            "paid_at": paid_at.isoformat(),
        },
    )

    assert response.status_code == 200

    payment = payment_repository.get_payment_by_id(payment_id)

    assert payment["status"] == "PAID"
    assert payment["paid_at"] == paid_at

def test_mark_payment_as_paid_returns_404_for_nonexistent_payment(
    api_client,
):
    paid_at = datetime(2027, 11, 1, 14, 30, 0)

    response = api_client.put(
        "/api/payments/999999/paid",
        json={
            "paid_at": paid_at.isoformat(),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"

def test_mark_payment_as_paid_returns_409_for_already_paid_payment(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=1,
        check_in=date(2027, 11, 10),
        check_out=date(2027, 11, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="DEPOSIT",
        amount=Decimal("500.00"),
    )

    paid_at = datetime(2027, 11, 1, 14, 30, 0)

    payment_repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=paid_at,
    )

    response = api_client.put(
        f"/api/payments/{payment_id}/paid",
        json={
            "paid_at": paid_at.isoformat(),
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Payment is already PAID"

def test_get_payment_report_returns_200(
    db_connection,
    api_client,
):
    reservation_repository = ReservationRepository(db_connection)
    payment_repository = PaymentRepository(db_connection)

    reservation_id = reservation_repository.create(
        cottage_id=1,
        source_id=4,  # BELVILLA
        check_in=date(2028, 3, 10),
        check_out=date(2028, 3, 17),
        guests_count=2,
    )

    payment_id = payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type="BALANCE",
        amount=Decimal("900.00"),
    )

    paid_at = datetime(2028, 3, 1, 14, 30, 0)

    payment_repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=paid_at,
    )

    response = api_client.get(
        "/api/payments/report",
        params={
            "start_date": "2028-03-01",
            "end_date": "2028-04-01",
            "vat_rate": 8,
            "source_code": "BELVILLA",
        },
    )
    print(response.status_code)
    print(response.json())
    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["payment_id"] == payment_id
    assert data[0]["source_code"] == "BELVILLA"
    assert data[0]["gross_amount"] == 900.0
    assert data[0]["net_amount"] == 833.33
    assert data[0]["vat_amount"] == 66.67