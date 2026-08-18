from datetime import datetime, date
from app.reservation_rules import find_available_cottages
from app.reservation_service import expire_pending_reservations


def test_pending_reservation_expires_after_expiration_time(
    db_connection,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                "2026-10-01",
                "2026-10-07",
                2,
                "PENDING",
                datetime(2026, 8, 17, 18, 0, 0),
            ),
        )

        reservation_id = cursor.lastrowid

    expired_count = expire_pending_reservations(
        db_connection,
        datetime(2026, 8, 17, 18, 1, 0),
    )

    assert expired_count == 1

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

    assert reservation["status"] == "EXPIRED"

def test_pending_reservation_does_not_expire_before_expiration_time(
    db_connection,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                "2026-10-01",
                "2026-10-07",
                2,
                "PENDING",
                datetime(2026, 8, 17, 18, 0, 0),
            ),
        )

        reservation_id = cursor.lastrowid

    expired_count = expire_pending_reservations(
        db_connection,
        datetime(2026, 8, 17, 17, 59, 59),
    )

    assert expired_count == 0

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

def test_pending_reservation_expires_exactly_at_expiration_time(
    db_connection,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                "2026-10-10",
                "2026-10-15",
                2,
                "PENDING",
                datetime(2026, 8, 17, 18, 0, 0),
            ),
        )

        reservation_id = cursor.lastrowid

    expired_count = expire_pending_reservations(
        db_connection,
        datetime(2026, 8, 17, 18, 0, 0),
    )

    assert expired_count == 1

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

    assert reservation["status"] == "EXPIRED"

def test_confirmed_reservation_is_not_expired(
    db_connection,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                "2026-10-20",
                "2026-10-25",
                2,
                "CONFIRMED",
                datetime(2026, 8, 17, 17, 0, 0),
            ),
        )

        reservation_id = cursor.lastrowid

    expired_count = expire_pending_reservations(
        db_connection,
        datetime(2026, 8, 17, 18, 0, 0),
    )

    assert expired_count == 0

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
def test_expired_reservation_no_longer_blocks_cottage(
    db_connection,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO reservations (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                1,
                1,
                "2026-10-20",
                "2026-10-25",
                2,
                "PENDING",
                datetime(2026, 8, 17, 17, 0, 0),
            ),
        )

        reservation_id = cursor.lastrowid

    expired_count = expire_pending_reservations(
        db_connection,
        datetime(2026, 8, 17, 18, 0, 0),
    )

    assert expired_count == 1

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                cottage_id,
                check_in,
                check_out,
                status
            FROM reservations
            WHERE id = %s
            """,
            (reservation_id,),
        )

        reservation = cursor.fetchone()

    assert reservation["status"] == "EXPIRED"

    available_cottages = find_available_cottages(
        cottage_ids=[1, 2, 3, 4, 5, 6],
        reservations=[reservation],
        new_check_in=date(2026, 10, 20),
        new_check_out=date(2026, 10, 25),
        blocks=[],
    )

    assert 1 in available_cottages


    