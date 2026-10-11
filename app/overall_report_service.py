from datetime import date
from decimal import Decimal

from pymysql.connections import Connection

from app.bank_transaction_service import list_bank_transactions
from app.repositories.reservation_repository import ReservationRepository


SOURCE_NAMES = {
    1: "Direct",
    2: "Booking",
    3: "Airbnb",
    4: "Belvilla",
    5: "Nocowanie.pl",
    6: "OtoNoclegi.pl",
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


def generate_cash_flow_report(
    connection: Connection,
    start_date: date,
    end_date: date,
):
    report = generate_overall_report(
        connection=connection,
        start_date=start_date,
        end_date=end_date,
    )
    transactions = list_bank_transactions(
        connection=connection,
        start_date=start_date,
        end_date=end_date,
    )
    transactions = [
        {
            **transaction,
            "source_name": SOURCE_NAMES.get(
                transaction["source_id"],
                f"Source #{transaction['source_id']}",
            ),
        }
        for transaction in transactions
    ]

    total_amount = sum(
        (
            transaction["amount"] or Decimal("0.00")
            for transaction in transactions
        ),
        Decimal("0.00"),
    )

    return {
        **report,
        "transactions": transactions,
        "total_amount": total_amount,
    }
