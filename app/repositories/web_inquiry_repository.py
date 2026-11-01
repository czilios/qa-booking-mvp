from datetime import date

from pymysql.connections import Connection


class WebInquiryRepository:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create(
        self,
        full_name: str,
        phone: str,
        email: str,
        check_in: date,
        check_out: date,
        guests_count: int,
        preferred_cottage_id: int | None,
        message: str | None,
        availability_found: bool,
        available_cottage_ids: list[int],
    ) -> int:
        available_cottage_ids_value = ",".join(
            str(cottage_id) for cottage_id in available_cottage_ids
        )
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO web_inquiries (
                    full_name,
                    phone,
                    email,
                    check_in,
                    check_out,
                    guests_count,
                    preferred_cottage_id,
                    message,
                    availability_found,
                    available_cottage_ids
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    full_name,
                    phone,
                    email,
                    check_in,
                    check_out,
                    guests_count,
                    preferred_cottage_id,
                    message,
                    availability_found,
                    available_cottage_ids_value,
                ),
            )
            return cursor.lastrowid

    def list_all(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    web_inquiries.id,
                    web_inquiries.full_name,
                    web_inquiries.phone,
                    web_inquiries.email,
                    web_inquiries.check_in,
                    web_inquiries.check_out,
                    web_inquiries.guests_count,
                    web_inquiries.preferred_cottage_id,
                    web_inquiries.message,
                    web_inquiries.availability_found,
                    web_inquiries.available_cottage_ids,
                    web_inquiries.status,
                    web_inquiries.reservation_id,
                    web_inquiries.offered_cottage_id,
                    web_inquiries.offered_check_in,
                    web_inquiries.offered_check_out,
                    web_inquiries.offered_total_amount,
                    web_inquiries.offered_deposit_amount,
                    web_inquiries.message_sent_at,
                    web_inquiries.created_at,
                    r.status AS reservation_status,
                    r.expires_at AS reservation_expires_at
                FROM web_inquiries
                LEFT JOIN reservations r ON r.id = web_inquiries.reservation_id
                ORDER BY web_inquiries.created_at DESC, web_inquiries.id DESC
                """
            )
            inquiries = cursor.fetchall()
            for inquiry in inquiries:
                stored_ids = inquiry["available_cottage_ids"]
                inquiry["available_cottage_ids"] = (
                    [int(value) for value in stored_ids.split(",") if value]
                    if stored_ids is not None
                    else None
                )
            return inquiries

    def update_status(self, inquiry_id: int, status: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE web_inquiries
                SET status = %s
                WHERE id = %s
                """,
                (status, inquiry_id),
            )

    def get_by_id_for_update(self, inquiry_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id, full_name, phone, email, check_in, check_out,
                    guests_count, preferred_cottage_id, status, reservation_id,
                    offered_cottage_id, offered_check_in, offered_check_out,
                    offered_total_amount, offered_deposit_amount, message_sent_at
                FROM web_inquiries
                WHERE id = %s
                FOR UPDATE
                """,
                (inquiry_id,),
            )
            return cursor.fetchone()

    def save_sent_offer(
        self,
        inquiry_id: int,
        cottage_id: int,
        check_in: date,
        check_out: date,
        total_amount,
        deposit_amount,
        message_sent_at,
    ) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE web_inquiries
                SET offered_cottage_id = %s,
                    offered_check_in = %s,
                    offered_check_out = %s,
                    offered_total_amount = %s,
                    offered_deposit_amount = %s,
                    message_sent_at = %s
                WHERE id = %s AND status = 'IN_PROGRESS' AND reservation_id IS NULL
                """,
                (
                    cottage_id,
                    check_in,
                    check_out,
                    total_amount,
                    deposit_amount,
                    message_sent_at,
                    inquiry_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Inquiry cannot accept an offer")

    def convert_to_reservation(
        self,
        inquiry_id: int,
        reservation_id: int,
    ) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE web_inquiries
                SET status = 'CONVERTED', reservation_id = %s
                WHERE id = %s AND reservation_id IS NULL
                """,
                (reservation_id, inquiry_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Inquiry already converted")
