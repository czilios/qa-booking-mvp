from datetime import datetime
from decimal import Decimal

from pymysql.connections import Connection


class PaymentRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create_payment(
        self,
        reservation_id: int,
        payment_type: str,
        amount: Decimal,
        status: str = "UNPAID",
        due_at: datetime | None = None,
    ) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payments (
                    reservation_id,
                    type,
                    amount,
                    status,
                    due_at
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    reservation_id,
                    payment_type,
                    amount,
                    status,
                    due_at,
                ),
            )

            return cursor.lastrowid

    def get_payment_by_id(self, payment_id: int):
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
                WHERE id = %s
                """,
                (payment_id,),
            )

            return cursor.fetchone()

    def get_payment_by_reservation_id(
        self,
        reservation_id: int,
    ):
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
                ORDER BY id
                """,
                (reservation_id,),
            )

            return cursor.fetchall()

    def get_deposit_payment_by_reservation_id(
        self,
        reservation_id: int,
    ):
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
                """,
                (reservation_id,),
            )

            return cursor.fetchone()

    def mark_payment_as_paid(
        self,
        payment_id: int,
        paid_at: datetime,
    ) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE payments
                SET
                    status = 'PAID',
                    paid_at = %s
                WHERE id = %s
                """,
                (
                    paid_at,
                    payment_id,
                ),
            )
    def get_deposit_payment_for_update(
    self,
    reservation_id: int,
    ):
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
        