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
    ):
        cottage_ids = (
            self.cottage_repository
            .get_active_cottage_ids()
        )

        reservations = (
            self.reservation_repository
            .get_active_reservations()
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