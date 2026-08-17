from datetime import date, datetime

from pymysql.connections import Connection


class ReservationRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create(
        self,
        cottage_id: int,
        source_id: int,
        check_in: date,
        check_out: date,
        guests_count: int,
        status: str = "PENDING",
        expires_at: datetime | None = None,
    ) -> int:
        with self.connection.cursor() as cursor:
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
                    cottage_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    expires_at,
                ),
            )

            return cursor.lastrowid

    def get_by_id(self, reservation_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    cottage_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    expires_at
                FROM reservations
                WHERE id = %s
                """,
                (reservation_id,),
            )

            return cursor.fetchone()

    def get_by_id_for_update(self, reservation_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    cottage_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    expires_at
                FROM reservations
                WHERE id = %s
                FOR UPDATE
                """,
                (reservation_id,),
            )

            return cursor.fetchone()

    def get_deposit_for_update(self, reservation_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    reservation_id,
                    type,
                    amount,
                    status,
                    due_at,
                    paid_at
                FROM payments
                WHERE reservation_id = %s
                  AND type = 'DEPOSIT'
                ORDER BY id
                LIMIT 1
                FOR UPDATE
                """,
                (reservation_id,),
            )

            return cursor.fetchone()

    def update_status(
        self,
        reservation_id: int,
        status: str,
    ) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reservations
                SET status = %s
                WHERE id = %s
                """,
                (
                    status,
                    reservation_id,
                ),
            )

    def expire_pending_reservations(
        self,
        now: datetime,
    ) -> int:
        with self.connection.cursor() as cursor:
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
    def get_by_id_for_update(self, reservation_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT
                id,
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                expires_at
            FROM reservations
            WHERE id = %s
            FOR UPDATE
            """,
            (reservation_id,),
        )

        return cursor.fetchone()