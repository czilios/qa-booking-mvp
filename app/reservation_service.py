from datetime import datetime
from pymysql.connections import Connection
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def confirm_reservation_after_deposit(
    connection,
    reservation_id: int,
) -> None:
    reservation_repository = ReservationRepository(connection)
    payment_repository = PaymentRepository(connection)

    reservation = reservation_repository.get_by_id_for_update(
        reservation_id
    )

    if reservation is None:
        raise ValueError("Reservation not found")

    if reservation["status"] != "PENDING":
        raise ValueError("Reservation is not PENDING")

    deposit = payment_repository.get_deposit_payment_for_update(
        reservation_id
    )

    if deposit is None:
        raise ValueError("Deposit not found")

    if deposit["status"] != "PAID":
        raise ValueError("Deposit is not PAID")

    reservation_repository.update_status(
        reservation_id,
        "CONFIRMED",
    )
    
def expire_pending_reservations(
    connection: Connection,
    now: datetime,
) -> int:
    repository = ReservationRepository(connection)

    return repository.expire_pending_reservations(now)