from datetime import datetime
from pymysql.connections import Connection


def confirm_reservation_after_deposit(
    connection: Connection,
    reservation_id: int,
) -> None:
    with connection.cursor() as cursor:
        # Check reservation
        cursor.execute(
            """
            SELECT id, status
            FROM reservations
            WHERE id = %s
            FOR UPDATE
            """,
            (reservation_id,),
        )

        reservation = cursor.fetchone()

        if reservation is None:
            raise ValueError("Reservation not found")

        if reservation["status"] != "PENDING":
            raise ValueError("Reservation is not PENDING")

        # Check deposit
        cursor.execute(
            """
            SELECT id, status
            FROM payments
            WHERE reservation_id = %s
              AND type = 'DEPOSIT'
            ORDER BY id
            LIMIT 1
            FOR UPDATE
            """,
            (reservation_id,),
        )

        deposit = cursor.fetchone()

        if deposit is None:
            raise ValueError("Deposit not found")

        if deposit["status"] != "PAID":
            raise ValueError("Deposit is not PAID")

        # Confirm reservation
        cursor.execute(
            """
            UPDATE reservations
            SET status = 'CONFIRMED'
            WHERE id = %s
            """,
            (reservation_id,),
        )
def expire_pending_reservations(
    connection: Connection,
    now: datetime,
) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE reservations
            SET status = 'EXPIRED'
            WHERE status = 'PENDING'
              AND expires_at IS NOT NULL
              AND expires_at <= %s
            """,
            (now,),
        )

        return cursor.rowcount