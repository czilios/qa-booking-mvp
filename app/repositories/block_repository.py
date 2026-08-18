class BlockRepository:
    def __init__(self, connection):
        self.connection = connection

    def get_active_blocks(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    cottage_id,
                    start_date,
                    end_date
                FROM blocks
                """
            )

            return cursor.fetchall()