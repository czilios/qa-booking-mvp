import pytest
from datetime import date

from app.reservation_rules import reservations_conflict


@pytest.mark.parametrize(
    "existing_check_in, existing_check_out, new_check_in, new_check_out, expected",
    [
        # Bezpośrednie połączenie pobytów — brak konfliktu
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 25),
            date(2026, 8, 30),
            False,
        ),

        # Nowa rezerwacja kończy się dokładnie w dniu rozpoczęcia istniejącej
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 15),
            date(2026, 8, 20),
            False,
        ),

        # Pełne pokrycie
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 20),
            date(2026, 8, 25),
            True,
        ),

        # Częściowe nachodzenie z lewej
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 19),
            date(2026, 8, 21),
            True,
        ),

        # Częściowe nachodzenie z prawej
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 24),
            date(2026, 8, 26),
            True,
        ),

        # Nowa rezerwacja znajduje się całkowicie wewnątrz istniejącej
        (
            date(2026, 8, 20),
            date(2026, 8, 25),
            date(2026, 8, 21),
            date(2026, 8, 24),
            True,
        ),
    ],
)
def test_reservations_conflict(
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

    assert result is expected