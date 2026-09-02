from datetime import date
from decimal import Decimal

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)
from app.repositories.reservation_repository import ReservationRepository


DIRECT_SOURCE_ID = 1
VAT_RATE = Decimal("0.08")


def generate_accounting_report(
    connection,
    start_date: date,
    end_date: date,
):
    bank_repository = BankTransactionRepository(connection)
    reservation_repository = ReservationRepository(connection)

    transactions = bank_repository.list_by_date_range(
        start_date=start_date,
        end_date=end_date,
    )

    direct_transactions = [
        transaction
        for transaction in transactions
        if transaction["source_id"] == DIRECT_SOURCE_ID
    ]

    booking_reservations = reservation_repository.get_accounting_booking_reservations_by_check_in_between(
        start_date=start_date,
        end_date=end_date,
        )
    for booking in booking_reservations:
            booking["gross_amount"] = (
                booking["total_amount"] or Decimal("0.00")
            ) + (
                booking["commission_amount"] or Decimal("0.00")
            )
    direct_gross = sum(
    (transaction["amount"] for transaction in direct_transactions),
    Decimal("0.00")
)

    booking_gross = sum(
        (booking["gross_amount"] for booking in booking_reservations),
        Decimal("0.00")
    )

    total_gross = direct_gross + booking_gross

    total_net = (
        total_gross / (Decimal("1.00") + VAT_RATE)
    ).quantize(Decimal("0.01"))

    total_vat = (
        total_gross - total_net
    ).quantize(Decimal("0.01"))

    return {
        "transactions": direct_transactions,
        "booking_reservations": booking_reservations,
        "total_gross": total_gross,
        "total_net": total_net,
        "total_vat": total_vat,
    }