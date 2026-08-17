from datetime import date


def reservations_conflict(
    existing_check_in: date,
    existing_check_out: date,
    new_check_in: date,
    new_check_out: date,
) -> bool:
    return (
        new_check_in < existing_check_out
        and new_check_out > existing_check_in
    )


def reservation_blocks_cottage(
    reservation: dict,
    new_check_in: date,
    new_check_out: date,
) -> bool:
    blocking_statuses = {"PENDING", "CONFIRMED"}

    if reservation["status"] not in blocking_statuses:
        return False

    return reservations_conflict(
        reservation["check_in"],
        reservation["check_out"],
        new_check_in,
        new_check_out,
    )


def block_blocks_cottage(
    block: dict,
    new_check_in: date,
    new_check_out: date,
) -> bool:
    return reservations_conflict(
        block["start_date"],
        block["end_date"],
        new_check_in,
        new_check_out,
    )


def cottage_is_available(
    cottage_id: int,
    reservations: list[dict],
    blocks: list[dict],
    new_check_in: date,
    new_check_out: date,
) -> bool:

    for reservation in reservations:
        if reservation["cottage_id"] != cottage_id:
            continue

        if reservation_blocks_cottage(
            reservation,
            new_check_in,
            new_check_out,
        ):
            return False

    for block in blocks:
        if block["cottage_id"] != cottage_id:
            continue

        if block_blocks_cottage(
            block,
            new_check_in,
            new_check_out,
        ):
            return False

    return True


def find_available_cottages(
    cottage_ids: list[int],
    reservations: list[dict],
    new_check_in: date,
    new_check_out: date,
    blocks: list[dict],
) -> list[int]:

    return [
        cottage_id
        for cottage_id in cottage_ids
        if cottage_is_available(
            cottage_id,
            reservations,
            blocks,
            new_check_in,
            new_check_out,
        )
    ]