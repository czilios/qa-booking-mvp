from datetime import date

from app.availability_service import AvailabilityService
from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository


def test_availability_service_returns_all_available_cottages(
    db_connection,
):
    reservation_repository = ReservationRepository(db_connection)
    block_repository = BlockRepository(db_connection)
    cottage_repository = CottageRepository(db_connection)

    availability_service = AvailabilityService(
        reservation_repository=reservation_repository,
        block_repository=block_repository,
        cottage_repository=cottage_repository,
    )

    available_cottages = availability_service.get_available_cottages(
        check_in=date(2027, 7, 10),
        check_out=date(2027, 7, 17),
    )

    assert available_cottages == [1, 2, 3, 4, 5, 6]

def test_reservation_blocks_cottage_availability(db_connection):
        reservation_repository = ReservationRepository(db_connection)
        block_repository = BlockRepository(db_connection)
        cottage_repository = CottageRepository(db_connection)

        availability_service = AvailabilityService(
            reservation_repository=reservation_repository,
            block_repository=block_repository,
            cottage_repository=cottage_repository,
        )

        # Create a reservation that overlaps with the availability check
        reservation_repository.create(
            cottage_id=1,
            source_id=1,
            check_in=date(2027, 7, 12),
            check_out=date(2027, 7, 15),
            guests_count=2,
        )

        available_cottages = availability_service.get_available_cottages(
            check_in=date(2027, 7, 10),
            check_out=date(2027, 7, 17),
        )

        assert available_cottages == [2, 3, 4, 5, 6]
def test_blocked_cottage_is_not_available(db_connection):
    reservation_repository = ReservationRepository(db_connection)
    block_repository = BlockRepository(db_connection)
    cottage_repository = CottageRepository(db_connection)

    availability_service = AvailabilityService(
        reservation_repository=reservation_repository,
        block_repository=block_repository,
        cottage_repository=cottage_repository,
    )

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO blocks (
                cottage_id,
                start_date,
                end_date,
                reason
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                1,
                date(2027, 7, 12),
                date(2027, 7, 15),
                "Maintenance",
            ),
        )

    available_cottages = availability_service.get_available_cottages(
        check_in=date(2027, 7, 10),
        check_out=date(2027, 7, 17),
    )

    assert available_cottages == [2, 3, 4, 5, 6]