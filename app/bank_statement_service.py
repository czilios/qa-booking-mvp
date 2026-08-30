from datetime import datetime
from decimal import Decimal

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)

class BankStatementReportService:
    def __init__(self, payment_repository):
        self.payment_repository = payment_repository

    def generate_payment_report(
        self,
        start_date: datetime,
        end_date: datetime,
    ):
        paid_payments = (
            self.payment_repository
            .get_paid_payments_between(start_date, end_date)
        )

        rows = []

        for payment in paid_payments:
            rows.append({
                "payment_id": payment["payment_id"],
                "reservation_id": payment["reservation_id"],
                "payment_type": payment["payment_type"],
                "amount": payment["amount"],
                "paid_at": payment["paid_at"],
                "cottage_id": payment["cottage_id"],
                "check_in": payment["check_in"],
                "check_out": payment["check_out"],
                "source_code": payment["source_code"],
                "source_name": payment["source_name"],
            })

        total_amount = sum(
            (row["amount"] for row in rows),
            Decimal("0.00"),
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "rows": rows,
            "total_amount": total_amount,
        }

    def generate_monthly_report(
    self,
    year: int,
    month: int,
    ):
        start_date = datetime(year, month, 1)

        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        report = self.generate_payment_report(
        start_date=start_date,
        end_date=end_date,
        )

        return {
        "year": year,
        "month": month,
        **report,
        }
    
    def generate_bank_statement_report(
    self,
    bank_transaction_repository,
    year: int,
    notes: str | None = None,
    ):
        months = []

        carry_over_gross = Decimal("0.00")
        carry_over_net = Decimal("0.00")
        carry_over_vat = Decimal("0.00")
        for month in range(1, 13):
            if month == 12:
                start_date = datetime(year, 12, 1)
                end_date = datetime(year + 1, 1, 1)
            else:
                start_date = datetime(year, month, 1)
                end_date = datetime(year, month + 1, 1)
            transactions = bank_transaction_repository.list_by_date_range(
                start_date=start_date.date(),
                end_date=end_date.date(),
                notes=notes,
            )

            monthly_gross = sum(
            (transaction["amount"] for transaction in transactions),
            Decimal("0.00"),
            )

            monthly_net = (
            monthly_gross / Decimal("1.08")
            ).quantize(Decimal("0.01"))

            monthly_vat = (
            monthly_gross - monthly_net
            ).quantize(Decimal("0.01"))

            total_gross = carry_over_gross + monthly_gross
            total_net = carry_over_net + monthly_net
            total_vat = carry_over_vat + monthly_vat

            months.append({
            "year": year,
            "month": month,

            "monthly_gross": monthly_gross,
            "monthly_net": monthly_net,
            "monthly_vat": monthly_vat,

            "carry_over_gross": carry_over_gross,
            "carry_over_net": carry_over_net,
            "carry_over_vat": carry_over_vat,
            "total_gross": total_gross,
            "total_net": total_net,
            "total_vat": total_vat,
            })

            carry_over_gross = total_gross
            carry_over_net = total_net
            carry_over_vat = total_vat

        return {
            "year": year,
            "months": months,
            "total_gross": carry_over_gross,
            "total_net": carry_over_net,
            "total_vat": carry_over_vat,
        }