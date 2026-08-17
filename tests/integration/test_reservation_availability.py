from datetime import date

from app.reservation_rules import find_available_cottages

def test_pending_reservation_blocks_cottage(db_connection):
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
            VALUES (
                1,
                1,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "PENDING",
            ),
        )

        cursor.execute(
            """
            SELECT cottage_id, check_in, check_out, status
            FROM reservations
            WHERE cottage_id = 1
              AND check_in = %s
              AND check_out = %s
            """,
            (
                date(2026, 8, 20),
                date(2026, 8, 25),
            ),
        )

        reservation = cursor.fetchone()

    available_cottages = find_available_cottages(
        cottage_ids=[1, 2, 3, 4, 5, 6],
        reservations=[reservation],
        new_check_in=date(2026, 8, 22),
        new_check_out=date(2026, 8, 24),
        blocks=[],
    )

    assert 1 not in available_cottages

def test_reservation_ending_on_new_check_in_does_not_block_cottage(
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
                status
            )
            VALUES (
                1,
                1,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "CONFIRMED",
            ),
        )

        cursor.execute(
            """
            SELECT
                cottage_id,
                check_in,
                check_out,
                status
            FROM reservations
            WHERE cottage_id = 1
              AND check_in = %s
              AND check_out = %s
            """,
            (
                date(2026, 8, 20),
                date(2026, 8, 25),
            ),
        )

        reservation = cursor.fetchone()

    available_cottages = find_available_cottages(
        cottage_ids=[1, 2, 3, 4, 5, 6],
        reservations=[reservation],
        new_check_in=date(2026, 8, 25),
        new_check_out=date(2026, 8, 30),
        blocks=[],
    )

    assert 1 in available_cottages

def test_overlapping_reservation_blocks_cottage(
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
                status
            )
            VALUES (
                1,
                1,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "CONFIRMED",
            ),
        )

        cursor.execute(
            """
            SELECT
                cottage_id,
                check_in,
                check_out,
                status
            FROM reservations
            WHERE cottage_id = 1
              AND check_in = %s
              AND check_out = %s
            """,
            (
                date(2026, 8, 20),
                date(2026, 8, 25),
            ),
        )

        reservation = cursor.fetchone()

    available_cottages = find_available_cottages(
        cottage_ids=[1, 2, 3, 4, 5, 6],
        reservations=[reservation],
        new_check_in=date(2026, 8, 24),
        new_check_out=date(2026, 8, 30),
        blocks=[],
    )

    assert 1 not in available_cottages

def test_block_and_confirmed_reservation_both_block_cottage(
    db_connection,
):
    with db_connection.cursor() as cursor:
        # Create administrative block
        cursor.execute(
            """
            INSERT INTO blocks (
                cottage_id,
                start_date,
                end_date,
                reason
            )
            VALUES (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                5,
                date(2026, 8, 20),
                date(2026, 8, 25),
                "Test blokady",
            ),
        )

        # Create confirmed reservation for the same cottage and dates
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
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                5,
                1,
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "CONFIRMED",
            ),
        )

        # Read reservations
        cursor.execute(
            """
            SELECT
                cottage_id,
                check_in,
                check_out,
                status
            FROM reservations
            WHERE cottage_id = %s
              AND check_in = %s
              AND check_out = %s
            """,
            (
                5,
                date(2026, 8, 20),
                date(2026, 8, 25),
            ),
        )

        reservations = cursor.fetchall()

        # Read blocks
        cursor.execute(
            """
            SELECT
                cottage_id,
                start_date,
                end_date
            FROM blocks
            WHERE cottage_id = %s
              AND start_date = %s
              AND end_date = %s
            """,
            (
                5,
                date(2026, 8, 20),
                date(2026, 8, 25),
            ),
        )

        blocks = cursor.fetchall()

    available_cottages = find_available_cottages(
        cottage_ids=[1, 2, 3, 4, 5, 6],
        reservations=reservations,
        new_check_in=date(2026, 8, 22),
        new_check_out=date(2026, 8, 24),
        blocks=blocks,
    )

    assert 5 not in available_cottages

def test_find_available_cottages_returns_only_available_cottages(
    db_connection,
):
    with db_connection.cursor() as cursor:
        # Cottage 1 - CONFIRMED reservation
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
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "CONFIRMED",
            ),
        )

        # Cottage 2 - PENDING reservation
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
                2,
                1,
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "PENDING",
            ),
        )

        # Cottage 3 - administrative block
        cursor.execute(
            """
            INSERT INTO blocks (
                cottage_id,
                start_date,
                end_date,
                reason
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                3,
                date(2026, 8, 20),
                date(2026, 8, 25),
                "Test blokady",
            ),
        )

        # Cottage 5 - CONFIRMED reservation
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
                5,
                1,
                date(2026, 8, 20),
                date(2026, 8, 25),
                2,
                "CONFIRMED",
            ),
        )

        # Read blocking reservations
        cursor.execute(
            """
            SELECT
                cottage_id,
                check_in,
                check_out,
                status
            FROM reservations
            WHERE status IN ('PENDING', 'CONFIRMED')
            """
        )

        reservations = cursor.fetchall()

        # Read blocks
        cursor.execute(
            """
            SELECT
                cottage_id,
                start_date,
                end_date
            FROM blocks
            """
        )

        blocks = cursor.fetchall()

    available_cottages = find_available_cottages(
        cottage_ids=[1, 2, 3, 4, 5, 6],
        reservations=reservations,
        new_check_in=date(2026, 8, 20),
        new_check_out=date(2026, 8, 25),
        blocks=blocks,
    )

    assert available_cottages == [4, 6]
