from datetime import datetime
from decimal import Decimal


class AccountingReportService:
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