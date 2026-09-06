from datetime import date
from decimal import Decimal

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)
from app.repositories.reservation_repository import ReservationRepository


DIRECT_SOURCE_ID = 1
VAT_RATE = Decimal("0.08")

MONTH_NAMES_PL = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}

MONTH_NAMES_PL_GENITIVE = {
    1: "stycznia",
    2: "lutego",
    3: "marca",
    4: "kwietnia",
    5: "maja",
    6: "czerwca",
    7: "lipca",
    8: "sierpnia",
    9: "września",
    10: "października",
    11: "listopada",
    12: "grudnia",
}

def calculate_vat_values(gross_amount: Decimal):
    net_amount = (
        gross_amount / (Decimal("1.00") + VAT_RATE)
    ).quantize(Decimal("0.01"))

    vat_amount = (
        gross_amount - net_amount
    ).quantize(Decimal("0.01"))

    return net_amount, vat_amount


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

    for transaction in direct_transactions:
        transaction["gross_amount"] = transaction["amount"]

        (
            transaction["net_amount"],
            transaction["vat_amount"],
        ) = calculate_vat_values(
            transaction["gross_amount"]
        )
        
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

        (
            booking["net_amount"],
            booking["vat_amount"],
        ) = calculate_vat_values(
            booking["gross_amount"]
        )

    total_gross = (
            sum(
                (transaction["gross_amount"] for transaction in direct_transactions),
                Decimal("0.00"),
            )
            + sum(
                (booking["gross_amount"] for booking in booking_reservations),
                Decimal("0.00"),
            )
        )

    total_net, total_vat = calculate_vat_values(total_gross)
            
    return {
        "transactions": direct_transactions,
        "booking_reservations": booking_reservations,
        "total_gross": total_gross,
        "total_net": total_net,
        "total_vat": total_vat,
    }

def generate_accounting_reports(
    connection,
    start_date: date,
    end_date: date,
):
    reports = []
    current_date = start_date
    carry_amount = Decimal("0.00")

    while current_date < end_date:
        if current_date.month == 12:
            next_month = date(current_date.year + 1, 1, 1)
        else:
            next_month = date(
                current_date.year,
                current_date.month + 1,
                1,
            )

        if next_month > end_date:
            next_month = end_date

        report = generate_accounting_report(
            connection=connection,
            start_date=current_date,
            end_date=next_month,
            
        )

        total_gross = report["total_gross"]
        report["month"] = current_date.month
        report["year"] = current_date.year
        report["month_name"] = MONTH_NAMES_PL[current_date.month]
        report["month_name_genitive"] = MONTH_NAMES_PL_GENITIVE[current_date.month]
        report["carry_amount"] = carry_amount
        report["grand_total"] = carry_amount + total_gross

        reports.append(report)

        carry_amount = report["grand_total"]
        current_date = next_month

    return reports