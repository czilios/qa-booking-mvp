from datetime import datetime
from decimal import Decimal

from pymysql.connections import Connection

from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def mark_payment_as_paid(
    connection: Connection,
    payment_id: int,
    paid_at: datetime,
) -> None:
    repository = PaymentRepository(connection)

    payment = repository.get_payment_by_id(payment_id)

    if payment is None:
        raise ValueError("Payment not found")

    if payment["status"] == "PAID":
        raise ValueError("Payment is already PAID")

    repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=paid_at,
    )


def create_payment(
    connection: Connection,
    reservation_id: int,
    payment_type: str,
    amount: Decimal,
    due_at: datetime | None = None,
) -> int:

    valid_payment_types = {"DEPOSIT", "BALANCE"}

    if payment_type not in valid_payment_types:
        raise ValueError("Invalid payment type")

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero")

    reservation_repository = ReservationRepository(connection)

    reservation = reservation_repository.get_by_id(reservation_id)

    if reservation is None:
        raise ValueError("Reservation not found")

    payment_repository = PaymentRepository(connection)

    return payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type=payment_type,
        amount=amount,
        due_at=due_at,
    )