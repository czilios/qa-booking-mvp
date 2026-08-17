from datetime import date

import pytest

from app.reservation_rules import reservations_conflict


@pytest.mark.parametrize(
    "existing_check_in, existing_check_out, new_check_in, new_check_out, expected",
    [
        # Overlap
        (
            date(2026, 8, 17),
            date(2026, 8, 23),
            date(2026, 8, 20),
            date(2026, 8, 25),
            True,
        ),

        # Same dates
        (
            date(2026, 8, 17),
            date(2026, 8, 23),
            date(2026, 8, 17),
            date(2026, 8, 23),
            True,
        ),

        # New reservation starts before existing reservation
        (
            date(2026, 8, 17),
            date(2026, 8, 23),
            date(2026, 8, 16),
            date(2026, 8, 18),
            True,
        ),

        # New reservation overlaps the end
        (
            date(2026, 8, 17),
            date(2026, 8, 23),
            date(2026, 8, 22),
            date(2026, 8, 25),
            True,
        ),

        # New reservation starts exactly at checkout
        (
            date(2026, 8, 17),
            date(2026, 8, 23),
            date(2026, 8, 23),
            date(2026, 8, 27),
            False,
        ),

        # New reservation ends exactly at existing check-in
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 15),
            date(2026, 8, 20),
            False,
        ),

        # New reservation is completely before existing reservation
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 15),
            date(2026, 8, 20),
            False,
        ),

        # New reservation is completely after existing reservation
        (
            date(2026, 8, 17),
            date(2026, 8, 23),
            date(2026, 8, 25),
            date(2026, 8, 30),
            False,
        ),

        # New reservation is completely inside existing reservation
        (
            date(2026, 8, 17),
            date(2026, 8, 25),
            date(2026, 8, 20),
            date(2026, 8, 22),
            True,
        ),
    ],
)
def test_reservation_conflict(
    existing_check_in,
    existing_check_out,
    new_check_in,
    new_check_out,
    expected,
):
    result = reservations_conflict(
        existing_check_in,
        existing_check_out,
        new_check_in,
        new_check_out,
    )

    assert result == expected