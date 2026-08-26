from datetime import datetime, date
from decimal import Decimal
from pymysql.connections import Connection
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository
from app.availability_service import AvailabilityService
from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository


def confirm_reservation_after_deposit(
    connection,
    reservation_id: int,
) -> None:
    reservation_repository = ReservationRepository(connection)
    payment_repository = PaymentRepository(connection)

    reservation = reservation_repository.get_by_id_for_update(
        reservation_id
    )

    if reservation is None:
        raise ValueError("Reservation not found")

    if reservation["status"] != "PENDING":
        raise ValueError("Reservation is not PENDING")

    deposit = payment_repository.get_deposit_payment_for_update(
        reservation_id
    )

    if deposit is None:
        raise ValueError("Deposit not found")

    if deposit["status"] != "PAID":
        raise ValueError("Deposit is not PAID")

    reservation_repository.update_status(
        reservation_id,
        "CONFIRMED",
    )
    
def expire_pending_reservations(
    connection: Connection,
    now: datetime,
) -> int:
    repository = ReservationRepository(connection)

    return repository.expire_pending_reservations(now)

def create_reservation(
    connection: Connection,
    cottage_id: int,
    source_id: int,
    check_in: datetime,
    check_out: datetime,
    guests_count: int,
    customer_id: int | None = None,
    total_amount: Decimal | None = None,
    accounting_included: bool = False,
) -> int:
    reservation_repository = ReservationRepository(connection)

    availability_service = AvailabilityService(
        reservation_repository=reservation_repository,
        block_repository=BlockRepository(connection),
        cottage_repository=CottageRepository(connection),
    )

    cottage_repository = CottageRepository(connection)
    cottage = cottage_repository.get_by_id(cottage_id)

    if cottage is None:
        raise ValueError("Cottage not found")

    if guests_count > cottage["capacity"]:
        raise ValueError("Too many guests for this cottage")

    available_cottages = availability_service.get_available_cottages(
        check_in=check_in,
        check_out=check_out,
    )

    if cottage_id not in available_cottages:
        raise ValueError("Cottage is not available")

    return reservation_repository.create(
        cottage_id=cottage_id,
        source_id=source_id,
        check_in=check_in,
        check_out=check_out,
        guests_count=guests_count,
        customer_id=customer_id,
        total_amount=total_amount,
        accounting_included=accounting_included,
)

def update_reservation(
    connection: Connection,
    reservation_id: int,
    cottage_id: int,
    source_id: int,
    check_in: date,
    check_out: date,
    guests_count: int,
) -> None:
    reservation_repository = ReservationRepository(connection)
    cottage_repository = CottageRepository(connection)

    cottage = cottage_repository.get_by_id(cottage_id)

    if cottage is None:
        raise ValueError("Cottage not found")

    if guests_count > cottage["capacity"]:
        raise ValueError("Too many guests for this cottage")

    availability_service = AvailabilityService(
        reservation_repository=reservation_repository,
        block_repository=BlockRepository(connection),
        cottage_repository=cottage_repository,
    )

    available_cottages = availability_service.get_available_cottages(
        check_in=check_in,
        check_out=check_out,
        exclude_reservation_id=reservation_id,
    )

    if cottage_id not in available_cottages:
        raise ValueError("Cottage is not available")

    reservation_repository.update(
        reservation_id=reservation_id,
        cottage_id=cottage_id,
        source_id=source_id,
        check_in=check_in,
        check_out=check_out,
        guests_count=guests_count,
    )
def cancel_reservation(
    connection: Connection,
    reservation_id: int,
) -> None:
    repository = ReservationRepository(connection)

    reservation = repository.get_by_id_for_update(
        reservation_id
    )

    if reservation is None:
        raise ValueError("Reservation not found")

    if reservation["status"] == "CANCELLED":
        raise ValueError("Reservation is already cancelled")

    repository.update_status(
        reservation_id=reservation_id,
        status="CANCELLED",
    )

def generate_accounting_report(
    connection: Connection,
    start_date: date,
    end_date: date,
):
    repository = ReservationRepository(connection)

    reservations = repository.get_confirmed_reservations_between(
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "reservations": reservations,
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

    return {
        "reservations": reservations,
    }

def create_historical_reservation(
    connection: Connection,
    cottage_id: int,
    source_id: int,
    check_in: date,
    check_out: date,
    guests_count: int,
    total_amount: Decimal,
    customer_id: int | None = None,
    notes: str | None = None,
    commission_amount: Decimal | None = None,
) -> int:
    reservation_repository = ReservationRepository(connection)

    accounting_included = source_id in (1, 2)

    return reservation_repository.create(
        cottage_id=cottage_id,
        source_id=source_id,
        check_in=check_in,
        check_out=check_out,
        guests_count=guests_count,
        customer_id=customer_id,
        status="CONFIRMED",
        total_amount=total_amount,
        accounting_included=accounting_included,
        notes=notes,
        commission_amount=commission_amount,
    )