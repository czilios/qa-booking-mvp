from datetime import date

import pytest

from app.reservation_rules import (
    find_available_cottages,
    reservation_blocks_cottage,
)


COTTAGES = [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize(
    "reservation_status",
    [
        "PENDING",
        "CONFIRMED",
    ],
)
def test_active_reservation_blocks_cottage(reservation_status):
    reservations = [
        {
            "cottage_id": 1,
            "check_in": date(2026, 8, 17),
            "check_out": date(2026, 8, 23),
            "status": reservation_status,
        }
    ]

    result = find_available_cottages(
        COTTAGES,
        reservations,
        date(2026, 8, 20),
        date(2026, 8, 25),
        [],
    )

    assert 1 not in result


@pytest.mark.parametrize(
    "reservation_status",
    [
        "CANCELLED",
        "EXPIRED",
    ],
)
def test_inactive_reservation_does_not_block_cottage(reservation_status):
    reservations = [
        {
            "cottage_id": 1,
            "check_in": date(2026, 8, 17),
            "check_out": date(2026, 8, 23),
            "status": reservation_status,
        }
    ]

    result = find_available_cottages(
        COTTAGES,
        reservations,
        date(2026, 8, 20),
        date(2026, 8, 25),
        [],
    )

    assert 1 in result


def test_checkout_and_next_checkin_are_available():
    reservations = [
        {
            "cottage_id": 1,
            "check_in": date(2026, 8, 17),
            "check_out": date(2026, 8, 23),
            "status": "CONFIRMED",
        }
    ]

    result = find_available_cottages(
        COTTAGES,
        reservations,
        date(2026, 8, 23),
        date(2026, 8, 27),
        [], 
    )

    assert 1 in result


def test_multiple_cottages_are_filtered_correctly():
    reservations = [
        {
            "cottage_id": 1,
            "check_in": date(2026, 8, 17),
            "check_out": date(2026, 8, 23),
            "status": "CONFIRMED",
        },
        {
            "cottage_id": 2,
            "check_in": date(2026, 8, 20),
            "check_out": date(2026, 8, 25),
            "status": "PENDING",
        },
        {
            "cottage_id": 6,
            "check_in": date(2026, 8, 22),
            "check_out": date(2026, 8, 30),
            "status": "CONFIRMED",
        },
    ]

    result = find_available_cottages(
        COTTAGES,
        reservations,
        date(2026, 8, 20),
        date(2026, 8, 23),
        [], 
    )

    assert result == [3, 4, 5]

def test_blocked_cottage_is_not_available():
    reservations = []

    blocks = [
        {
            "cottage_id": 3,
            "start_date": date(2026, 8, 20),
            "end_date": date(2026, 8, 25),
        }
    ]

    result = find_available_cottages(
        COTTAGES,
        reservations,
        date(2026, 8, 22),
        date(2026, 8, 24),
        blocks,
    )

    assert 3 not in result

def test_pending_reservation_blocks_cottage():
    reservation = {
        "cottage_id": 1,
        "check_in": date(2026, 8, 17),
        "check_out": date(2026, 8, 23),
        "status": "PENDING",
    }

    result = reservation_blocks_cottage(
        reservation,
        date(2026, 8, 20),
        date(2026, 8, 25),
    )

    assert result is True

def test_cancelled_reservation_does_not_block_cottage():
    reservation = {
        "cottage_id": 1,
        "check_in": date(2026, 8, 17),
        "check_out": date(2026, 8, 23),
        "status": "CANCELLED",
    }

    result = reservation_blocks_cottage(
        reservation,
        date(2026, 8, 20),
        date(2026, 8, 25),
    )

    assert result is False