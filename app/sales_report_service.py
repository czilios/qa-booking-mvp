from datetime import date
from decimal import Decimal
from pymysql.connections import Connection


from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def generate_sales_report(
    connection: Connection,
    start_date: date,
    end_date: date,
):
    repository = ReservationRepository(connection)

    reservations = repository.get_confirmed_reservations_by_check_in_between(
        start_date=start_date,
        end_date=end_date,
    )
    payment_repository = PaymentRepository(connection)

    reservation_ids = [
    reservation["id"]
    for reservation in reservations
    ]

    paid_amounts = payment_repository.get_paid_amount_by_reservation_ids(
    reservation_ids
    )

    for reservation in reservations:
        paid_amount = paid_amounts.get(
        reservation["id"],
        Decimal("0.00"),
        )

        reservation["paid_amount"] = paid_amount
        reservation["balance"] = (
            reservation["total_amount"] or Decimal("0.00")
        ) - paid_amount

    total_amount = sum(
    (
        reservation["total_amount"] or Decimal("0.00")
        for reservation in reservations
    ),
    Decimal("0.00"),
    )
    by_source = {}

    for reservation in reservations:
        source_id = reservation["source_id"]
        amount = reservation["total_amount"] or Decimal("0.00")

        by_source[source_id] = (
            by_source.get(source_id, Decimal("0.00"))
            + amount
        )

    return {
    "reservations": reservations,
    "total_amount": total_amount,
    "by_source": by_source,
    }