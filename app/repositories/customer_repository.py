from pymysql.connections import Connection


class CustomerRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        email: str | None = None,
    ) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO customers (
                    first_name,
                    last_name,
                    phone,
                    email
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    first_name,
                    last_name,
                    phone,
                    email,
                ),
            )

            return cursor.lastrowid

    def get_by_id(
        self,
        customer_id: int,
    ):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    first_name,
                    last_name,
                    phone,
                    email,
                    notes,
                    created_at,
                    updated_at
                FROM customers
                WHERE id = %s
                """,
                (customer_id,),
            )

            return cursor.fetchone()
    def update(
    self,
    customer_id: int,
    first_name: str,
    last_name: str,
    phone: str,
    email: str | None = None,
) -> None:
         with self.connection.cursor() as cursor:
             cursor.execute(
            """
            UPDATE customers
            SET
                first_name = %s,
                last_name = %s,
                phone = %s,
                email = %s
            WHERE id = %s
            """,
            (
                first_name,
                last_name,
                phone,
                email,
                customer_id,
            ),
        )