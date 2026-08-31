from datetime import date, datetime
from decimal import Decimal
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
        customer_id: int | None = None,
        status: str = "PENDING",
        expires_at: datetime | None = None,
        total_amount: Decimal | None = None,
        accounting_included: bool = False,
        notes: str | None = None,
        commission_amount: Decimal | None = None,
    ) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reservations (
                    cottage_id,
                    customer_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    expires_at,
                    total_amount,
                    accounting_included,
                    notes,
                    commission_amount
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    cottage_id,
                    customer_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    expires_at,
                    total_amount,
                    accounting_included,
                    notes,
                    commission_amount
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
                    customer_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    expires_at,
                    total_amount,
                    accounting_included,
                    notes,
                    commission_amount
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
                    customer_id,
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
                    customer_id,
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

    def get_confirmed_reservations_between(
        self,
        start_date: date,
        end_date: date,
    ):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    cottage_id,
                    customer_id,
                    source_id,
                    check_in,
                    check_out,
                    guests_count,
                    status,
                    total_amount,
                    accounting_included
                FROM reservations
                WHERE status = 'CONFIRMED'
                AND accounting_included = TRUE
                AND check_out >= %s
                AND check_out < %s
                ORDER BY check_out, id
                """,
                (
                    start_date,
                    end_date,
                ),
            )

            return cursor.fetchall()
        
    def get_all_confirmed_reservations_between(
    self,
    start_date: date,
    end_date: date,
    ):
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT
                id,
                cottage_id,
                customer_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                total_amount,
                accounting_included
            FROM reservations
            WHERE status = 'CONFIRMED'
              AND check_out >= %s
              AND check_out < %s
            ORDER BY check_out, id
            """,
            (
                start_date,
                end_date,
            ),
        )

        return cursor.fetchall()
    def get_confirmed_reservations_by_check_in_between(
    self,
    start_date: date,
    end_date: date,
    ):
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT
                id,
                cottage_id,
                customer_id,
                source_id,
                check_in,
                check_out,
                guests_count,
                status,
                total_amount,
                accounting_included
            FROM reservations
            WHERE status = 'CONFIRMED'
              AND check_in >= %s
              AND check_in < %s
            ORDER BY check_in, id
            """,
            (
                start_date,
                end_date,
            ),
        )

        return cursor.fetchall()
    
    def get_confirmed_reservations_by_check_in_between(
    self,
    start_date: date,
    end_date: date,
    ):
        with self.connection.cursor() as cursor:
            cursor.execute(
            """
            SELECT
                r.id,
                r.cottage_id,
                r.customer_id,
                r.source_id,
                r.check_in,
                r.check_out,
                r.guests_count,
                r.status,
                r.total_amount,
                r.accounting_included,
                rs.code AS source_code,
                rs.name AS source_name,
                c.phone
            FROM reservations r
            JOIN reservation_sources rs
                ON rs.id = r.source_id
            LEFT JOIN customers c
                ON c.id = r.customer_id
            WHERE r.status = 'CONFIRMED'
            AND r.check_in >= %s
            AND r.check_in < %s
            ORDER BY r.check_in, r.id
            """,
            (
                start_date,
                end_date,
            ),
        )

        return cursor.fetchall()
    