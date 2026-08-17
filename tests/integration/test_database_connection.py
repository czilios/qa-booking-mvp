from app.database import get_connection


def test_database_connection():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS result")
            row = cursor.fetchone()

        assert row["result"] == 1

    finally:
        connection.close()