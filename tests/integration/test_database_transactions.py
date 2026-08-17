def test_database_transaction_is_rolled_back(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO cottages (name, capacity, active)
            VALUES ('TEST_COTTAGE', 4, TRUE)
            """
        )

        cursor.execute(
            "SELECT COUNT(*) AS cottage_count "
            "FROM cottages "
            "WHERE name = 'TEST_COTTAGE'"
        )

        row = cursor.fetchone()

    assert row["cottage_count"] == 1

def test_test_cottage_was_not_persisted(db_connection):
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS cottage_count
            FROM cottages
            WHERE name = 'TEST_COTTAGE'
            """
        )

        row = cursor.fetchone()

    assert row["cottage_count"] == 0