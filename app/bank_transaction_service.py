from datetime import date, datetime
from decimal import Decimal

from pymysql.connections import Connection

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import confirm_reservation_after_deposit


def list_bank_transactions(
    connection: Connection,
    start_date: date,
    end_date: date,
    notes: str | None = None,

):
    repository = BankTransactionRepository(connection)

    return repository.list_by_date_range(
        start_date=start_date,
        end_date=end_date,
        notes=notes,
    )


def sum_bank_transactions(
    connection: Connection,
    start_date: date,
    end_date: date,
    notes: str | None = None,
) -> Decimal:
    repository = BankTransactionRepository(connection)

    return repository.sum_by_date_range(
        start_date=start_date,
        end_date=end_date,
        notes=notes,
    )

def create_bank_transaction(
    connection: Connection,
    transaction_date: date,
    source_id: int,
    cottage_id: int | None,
    amount: Decimal,
    description: str | None = None,
    notes: str | None = None,
    reservation_number: str | None = None,
) -> int:
    repository = BankTransactionRepository(connection)

    if reservation_number:
        if source_id != 1:
            raise ValueError("Ręczne przypisanie rezerwacji jest dostępne tylko dla Direct")

        reservation_id, reservation, deposit = get_direct_pending_deposit(
            connection,
            reservation_number,
        )
        if Decimal(str(deposit["amount"])) != amount:
            raise ValueError("Kwota wpływu musi odpowiadać oczekiwanemu zadatkowi")

        payment_repository = PaymentRepository(connection)
        transaction_id = repository.create(
            transaction_date=transaction_date,
            source_id=source_id,
            cottage_id=reservation["cottage_id"],
            amount=amount,
            description=description,
            notes=notes,
        )
        payment_repository.mark_payment_as_paid(
            payment_id=deposit["id"],
            paid_at=datetime.combine(transaction_date, datetime.min.time()),
            bank_transaction_id=transaction_id,
        )
        confirm_reservation_after_deposit(connection, reservation_id)
        return transaction_id

    return repository.create(
        transaction_date=transaction_date,
        source_id=source_id,
        cottage_id=cottage_id,
        amount=amount,
        description=description,
        notes=notes,
    )


def get_direct_pending_deposit(connection, reservation_number: str):
    reservation_id_text = reservation_number.strip().removeprefix("#")
    if not reservation_id_text.isdigit():
        raise ValueError("Numer rezerwacji musi mieć format #12323")

    reservation_id = int(reservation_id_text)
    reservation = ReservationRepository(connection).get_by_id(reservation_id)
    if reservation is None:
        raise ValueError("Nie znaleziono rezerwacji")
    if reservation["source_id"] != 1:
        raise ValueError("Można przypisać tylko rezerwację Direct")
    if reservation["status"] != "PENDING":
        raise ValueError("Rezerwacja Direct nie oczekuje na zadatek")

    deposit = PaymentRepository(connection).get_deposit_payment_by_reservation_id(
        reservation_id
    )
    if deposit is None:
        raise ValueError("Rezerwacja nie ma zaplanowanego zadatku")
    if deposit["status"] != "UNPAID":
        raise ValueError("Zadatek dla tej rezerwacji jest już rozliczony")

    return reservation_id, reservation, deposit

