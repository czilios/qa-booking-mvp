class CottageRepository:
    def __init__(self, connection):
        self.connection = connection

    def get_active_cottage_ids(self, guests_count: int | None = None):
        with self.connection.cursor() as cursor:
            if guests_count is None:
                cursor.execute(
                    """
                    SELECT id
                    FROM cottages
                    WHERE active = 1
                    ORDER BY id
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT id
                    FROM cottages
                    WHERE active = 1
                      AND capacity >= %s
                    ORDER BY id
                    """,
                    (guests_count,),
                )

            return [row["id"] for row in cursor.fetchall()]
    def get_by_id(self, cottage_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT
                id,
                name,
                capacity,
                active
            FROM cottages
            WHERE id = %s
            """,
            (cottage_id,),
        )

        return cursor.fetchone()

    def get_by_id_for_update(self, cottage_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, capacity, active
                FROM cottages
                WHERE id = %s
                FOR UPDATE
                """,
                (cottage_id,),
            )
            return cursor.fetchone()
