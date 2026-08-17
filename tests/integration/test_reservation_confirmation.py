import pytest
from datetime import date

from app.reservation_service import confirm_reservation_after_deposit


def test_paid_deposit_confirms_pending_reservation(db_connection):
    with db_connection.cursor() as cursor:
        # Create pending reservation
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                date(2026, 9, 1),
                date(2026, 9, 7),
                2,
                "PENDING",
            ),
        )

        reservation_id = cursor.lastrowid

        # Create paid deposit
        cursor.execute(
            """
            INSERT INTO payments (
                reservation_id,
                type,
                amount,
                status,
                paid_at
            )
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (
                reservation_id,
                "DEPOSIT",
                500.00,
                "PAID",
            ),
        )

    # Business operation
    confirm_reservation_after_deposit(
        db_connection,
        reservation_id,
    )

    # Verify reservation status
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status
            FROM reservations
            WHERE id = %s
            """,
            (reservation_id,),
        )

        reservation = cursor.fetchone()

    assert reservation["status"] == "CONFIRMED"
def test_unpaid_deposit_does_not_confirm_reservation(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                date(2026, 9, 10),
                date(2026, 9, 15),
                2,
                "PENDING",
            ),
        )

        reservation_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO payments (
                reservation_id,
                type,
                amount,
                status
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                reservation_id,
                "DEPOSIT",
                500.00,
                "UNPAID",
            ),
        )

    with pytest.raises(ValueError, match="Deposit is not PAID"):
        confirm_reservation_after_deposit(
            db_connection,
            reservation_id,
        )

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status
            FROM reservations
            WHERE id = %s
            """,
            (reservation_id,),
        )

        reservation = cursor.fetchone()

    assert reservation["status"] == "PENDING"

def test_missing_deposit_does_not_confirm_reservation(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                date(2026, 9, 20),
                date(2026, 9, 25),
                2,
                "PENDING",
            ),
        )

        reservation_id = cursor.lastrowid

    with pytest.raises(ValueError, match="Deposit not found"):
        confirm_reservation_after_deposit(
            db_connection,
            reservation_id,
        )

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status
            FROM reservations
            WHERE id = %s
            """,
            (reservation_id,),
        )

        reservation = cursor.fetchone()

    assert reservation["status"] == "PENDING"

def test_confirmed_reservation_cannot_be_confirmed_again(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                date(2026, 10, 1),
                date(2026, 10, 7),
                2,
                "CONFIRMED",
            ),
        )

        reservation_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO payments (
                reservation_id,
                type,
                amount,
                status,
                paid_at
            )
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (
                reservation_id,
                "DEPOSIT",
                500.00,
                "PAID",
            ),
        )

    with pytest.raises(ValueError, match="Reservation is not PENDING"):
        confirm_reservation_after_deposit(
            db_connection,
            reservation_id,
        )
