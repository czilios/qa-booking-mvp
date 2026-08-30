from datetime import date
from decimal import Decimal

from pymysql.connections import Connection


class BankTransactionRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create(
        self,
        transaction_date: date,
        source_id: int,
        cottage_id: int | None,
        amount: Decimal,
        description: str | None = None,
        notes: str | None = None,
    ) -> int:
        if amount <= Decimal("0.00"):
            raise ValueError("Transaction amount must be greater than zero")

        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO bank_transactions (
                    transaction_date,
                    source_id,
                    cottage_id,
                    amount,
                    description,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_date,
                    source_id,
                    cottage_id,
                    amount,
                    description,
                    notes,
                ),
            )

            return cursor.lastrowid

    def get_by_id(self, transaction_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    transaction_date,
                    source_id,
                    cottage_id,
                    amount,
                    description,
                    notes
                FROM bank_transactions
                WHERE id = %s
                """,
                (transaction_id,),
            )

            return cursor.fetchone()
    def list_by_date_range(
    self,
    start_date: date,
    end_date: date,
    notes: str | None = None,
    ):
        with self.connection.cursor() as cursor:
            if notes is None:
                cursor.execute(
                """
                SELECT
                    id,
                    transaction_date,
                    source_id,
                    cottage_id,
                    amount,
                    description,
                    notes
                FROM bank_transactions
                WHERE transaction_date >= %s
                AND transaction_date < %s
                ORDER BY transaction_date, id
                """,
                (start_date, end_date),
                )
            else:
                cursor.execute(
                """
                SELECT
                    id,
                    transaction_date,
                    source_id,
                    cottage_id,
                    amount,
                    description,
                    notes
                FROM bank_transactions
                WHERE transaction_date >= %s
                AND transaction_date < %s
                AND notes = %s
                ORDER BY transaction_date, id
                """,
                (start_date, end_date, notes),
            )

        return cursor.fetchall()
   
    def sum_by_date_range(
    self,
    start_date: date,
    end_date: date,
    notes: str | None = None,
    ):
        with self.connection.cursor() as cursor:
            if notes is None:
                cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_transactions
                WHERE transaction_date >= %s
                  AND transaction_date < %s
                """,
                (start_date, end_date),
            )
            else:
                cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_transactions
                WHERE transaction_date >= %s
                  AND transaction_date < %s
                  AND notes = %s
                """,
                (start_date, end_date, notes),
            )

        return cursor.fetchone()["total"]
    
    def sum_by_source_and_date_range(
    self,
    source_id: int,
    start_date: date,
    end_date: date,
    notes: str | None = None,
    ):
        with self.connection.cursor() as cursor:
            if notes is None:
                cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_transactions
                WHERE source_id = %s
                  AND transaction_date >= %s
                  AND transaction_date < %s
                """,
                (source_id, start_date, end_date),
            )
            else:
                cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_transactions
                WHERE source_id = %s
                  AND transaction_date >= %s
                  AND transaction_date < %s
                  AND notes = %s
                """,
                (source_id, start_date, end_date, notes),
            )

            return cursor.fetchone()["total"]
        
    def sum_by_cottage_and_date_range(
    self,
    cottage_id: int,
    start_date: date,
    end_date: date,
    notes: str | None = None,
    ):
        with self.connection.cursor() as cursor:
            if notes is None:
                cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_transactions
                WHERE cottage_id = %s
                  AND transaction_date >= %s
                  AND transaction_date < %s
                """,
                (cottage_id, start_date, end_date),
            )
            else:
                cursor.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_transactions
                WHERE cottage_id = %s
                  AND transaction_date >= %s
                  AND transaction_date < %s
                  AND notes = %s
                """,
                (cottage_id, start_date, end_date, notes),
            )

        return cursor.fetchone()["total"]