from app.reservation_rules import find_available_cottages


class AvailabilityService:
    def __init__(
        self,
        reservation_repository,
        block_repository,
        cottage_repository,
    ):
        self.reservation_repository = reservation_repository
        self.block_repository = block_repository
        self.cottage_repository = cottage_repository

    def get_available_cottages(
    self,
    check_in,
    check_out,
    exclude_reservation_id=None,
    lock_reservations=False,
    reservation_cottage_id=None,
    guests_count=None,
    ):
        cottage_ids = (
            self.cottage_repository
            .get_active_cottage_ids(guests_count=guests_count)
        )

        reservation_reader = (
            self.reservation_repository.get_active_reservations_for_update
            if lock_reservations
            else self.reservation_repository.get_active_reservations
        )
        reservations = (
            reservation_reader(reservation_cottage_id)
            if lock_reservations
            else reservation_reader()
        )

        blocks = (
            self.block_repository
            .get_active_blocks()
        )

        return find_available_cottages(
            cottage_ids=cottage_ids,
            reservations=reservations,
            new_check_in=check_in,
            new_check_out=check_out,
            blocks=blocks,
            exclude_reservation_id=exclude_reservation_id,
        )
