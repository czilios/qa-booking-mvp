from datetime import date
from decimal import Decimal

from pymysql.connections import Connection

from app.repositories.reservation_repository import ReservationRepository


SOURCE_NAMES = {
    1: "Direct",
    2: "Booking",
    4: "Belvilla",
}


def generate_overall_report(
    connection: Connection,
    start_date: date,
    end_date: date,
):
    repository = ReservationRepository(connection)

    reservations = repository.get_all_confirmed_reservations_between(
        start_date=start_date,
        end_date=end_date,
    )

    rows = []

    for reservation in reservations:
        rows.append({
            **reservation,
            "source_name": SOURCE_NAMES.get(
                reservation["source_id"],
                f"Source #{reservation['source_id']}",
            ),
        })

    total_amount = sum(
        (
            row["total_amount"] or Decimal("0.00")
            for row in rows
        ),
        Decimal("0.00"),
    )

    return {
        "reservations": rows,
        "total_amount": total_amount,
    }