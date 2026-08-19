from datetime import date

from app.repositories.customer_repository import CustomerRepository
from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import create_reservation


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