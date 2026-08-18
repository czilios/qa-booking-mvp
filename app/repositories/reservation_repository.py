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
            if cursor.rowcount == 0:
                raise ValueError("Reservation not found")
        

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
    def get_active_reservations(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT
                id,
                cottage_id,
                check_in,
                check_out,
                status
            FROM reservations
            WHERE status IN ('PENDING', 'CONFIRMED')
            """
        )

        return cursor.fetchall()
    def update(
    self,
    reservation_id: int,
    cottage_id: int,
    source_id: int,
    check_in: date,
    check_out: date,
    guests_count: int,
) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            UPDATE reservations
            SET
                cottage_id = %s,
                source_id = %s,
                check_in = %s,
                check_out = %s,
                guests_count = %s
            WHERE id = %s
            """,
            (
                cottage_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                reservation_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError("Reservation not found")
    