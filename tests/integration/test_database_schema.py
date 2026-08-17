from app.database import get_connection


def test_required_tables_exist():
    expected_tables = {
        "cottages",
        "customers",
        "reservations",
    }

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            rows = cursor.fetchall()

        actual_tables = {
            next(iter(row.values()))
            for row in rows
        }

        assert expected_tables.issubset(actual_tables)

    finally:
        connection.close()


def test_database_contains_six_cottages():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS cottage_count FROM cottages")
            row = cursor.fetchone()

        assert row["cottage_count"] == 6

    finally:
        connection.close()


def test_all_cottages_have_capacity_four():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, capacity
                FROM cottages
                ORDER BY id
                """
            )
            cottages = cursor.fetchall()

        assert len(cottages) == 6
        assert all(cottage["capacity"] == 4 for cottage in cottages)

    finally:
        connection.close()


def test_all_cottages_are_active():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, active
                FROM cottages
                ORDER BY id
                """
            )
            cottages = cursor.fetchall()

        assert len(cottages) == 6
        assert all(cottage["active"] for cottage in cottages)

    finally:
        connection.close()