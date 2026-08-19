from datetime import datetime, date
from decimal import Decimal

from pymysql.connections import Connection

from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository


def mark_payment_as_paid(
    connection: Connection,
    payment_id: int,
    paid_at: datetime,
) -> None:
    repository = PaymentRepository(connection)

    payment = repository.get_payment_by_id(payment_id)

    if payment is None:
        raise ValueError("Payment not found")

    if payment["status"] == "PAID":
        raise ValueError("Payment is already PAID")

    repository.mark_payment_as_paid(
        payment_id=payment_id,
        paid_at=paid_at,
    )


def create_payment(
    connection: Connection,
    reservation_id: int,
    payment_type: str,
    amount: Decimal,
    due_at: datetime | None = None,
) -> int:

    valid_payment_types = {"DEPOSIT", "BALANCE"}

    if payment_type not in valid_payment_types:
        raise ValueError("Invalid payment type")

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero")

    reservation_repository = ReservationRepository(connection)

    reservation = reservation_repository.get_by_id(reservation_id)

    if reservation is None:
        raise ValueError("Reservation not found")

    payment_repository = PaymentRepository(connection)

    return payment_repository.create_payment(
        reservation_id=reservation_id,
        payment_type=payment_type,
        amount=amount,
        due_at=due_at,
    )

def generate_payment_report(
    connection: Connection,
    start_date: date,
    end_date: date,
    vat_rate: Decimal,
    source_code: str | None = None,
):
    payment_repository = PaymentRepository(connection)

    payments = payment_repository.get_paid_payments_between(
        start_date=start_date,
        end_date=end_date,
        source_code=source_code,
    )

    vat_rate = Decimal(str(vat_rate))

    report_rows = []

    for payment in payments:
        gross = Decimal(payment["amount"])

        if vat_rate == 0:
            net = gross
            vat = Decimal("0.00")
        else:
            net = (
                gross
                / (Decimal("1") + vat_rate / Decimal("100"))
            ).quantize(
                Decimal("0.01")
            )

            vat = (gross - net).quantize(
                Decimal("0.01")
            )

        report_rows.append(
            {
                "payment_id": payment["payment_id"],
                "reservation_id": payment["reservation_id"],
                "payment_type": payment["payment_type"],
                "gross_amount": gross,
                "net_amount": net,
                "vat_amount": vat,
                "vat_rate": vat_rate,
                "paid_at": payment["paid_at"],
                "cottage_id": payment["cottage_id"],
                "check_in": payment["check_in"],
                "check_out": payment["check_out"],
                "source_code": payment["source_code"],
                "source_name": payment["source_name"],
            }
        )

    return report_rows