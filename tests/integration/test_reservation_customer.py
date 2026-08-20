from datetime import date

from app.availability_service import AvailabilityService
from app.reservation_service import create_reservation

from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.reservation_repository import ReservationRepository


def test_create_reservation_stores_customer_id(db_connection):
    customer_repository = CustomerRepository(db_connection)

    customer_id = customer_repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
        email="jan@example.com",
    )

    reservation_id = create_reservation(
        connection=db_connection,
        customer_id=customer_id,
        cottage_id=1,
        source_id=1,
        check_in=date(2028, 5, 10),
        check_out=date(2028, 5, 17),
        guests_count=2,
    )

    reservation_repository = ReservationRepository(db_connection)

    reservation = reservation_repository.get_by_id(reservation_id)

    assert reservation["customer_id"] == customer_id

def test_created_reservation_blocks_cottage(db_connection):
    customer_repository = CustomerRepository(db_connection)

    customer_id = customer_repository.create(
        first_name="Jan",
        last_name="Kowalski",
        phone="+48666777567",
        email="jan@example.com",
    )

    reservation_id = create_reservation(
        connection=db_connection,
        customer_id=customer_id,
        cottage_id=1,
        source_id=1,
        check_in=date(2028, 5, 10),
        check_out=date(2028, 5, 17),
        guests_count=2,
    )

    availability_service = AvailabilityService(
        reservation_repository=ReservationRepository(db_connection),
        block_repository=BlockRepository(db_connection),
        cottage_repository=CottageRepository(db_connection),
    )

    available_cottages = availability_service.get_available_cottages(
        check_in=date(2028, 5, 10),
        check_out=date(2028, 5, 17),
    )

    assert 1 not in available_cottages

def test_created_reservation_overbooking_protection(db_connection):
    customer_repository = CustomerRepository(db_connection)

    customer_id = customer_repository.create(
        first_name="Janina",
        last_name="Kowalski",
        phone="+48646777567",
        email="janina@example.com",
    )
    create_reservation(
            connection=db_connection,
            customer_id=customer_id,
            cottage_id=1,
            source_id=1,
            check_in=date(2028, 5, 10),
            check_out=date(2028, 5, 17),
            guests_count=2,
        )
    
    availability_service = AvailabilityService(
            reservation_repository=ReservationRepository(db_connection),
            block_repository=BlockRepository(db_connection),
            cottage_repository=CottageRepository(db_connection),
        )
    
    available_cottages = availability_service.get_available_cottages(
            check_in=date(2028, 5, 7),
            check_out=date(2028, 5, 20),
        )
    
    assert 1 not in available_cottages