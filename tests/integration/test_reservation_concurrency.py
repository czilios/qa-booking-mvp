from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Lock

import pytest

from app.database import get_test_connection
from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import create_reservation


@pytest.mark.db
def test_parallel_creates_for_same_cottage_allow_at_most_one_booking(monkeypatch):
    """Two MariaDB transactions race for one cottage and overlapping dates."""
    cottage_id = 1
    check_in = date(2042, 7, 10)
    check_out = date(2042, 7, 14)
    start_together = Barrier(2)
    created_ids = []
    created_ids_lock = Lock()

    original_create = ReservationRepository.create

    def track_created_reservation(repository, *args, **kwargs):
        reservation_id = original_create(repository, *args, **kwargs)
        with created_ids_lock:
            created_ids.append(reservation_id)
        return reservation_id

    monkeypatch.setattr(ReservationRepository, "create", track_created_reservation)

    def attempt_booking():
        connection = get_test_connection()
        try:
            start_together.wait(timeout=10)
            try:
                reservation_id = create_reservation(
                    connection=connection,
                    cottage_id=cottage_id,
                    source_id=1,
                    check_in=check_in,
                    check_out=check_out,
                    guests_count=1,
                    is_test_data=True,
                )
            except ValueError as exc:
                if str(exc) != "Cottage is not available":
                    raise
                connection.rollback()
                return "conflict"

            connection.commit()
            return reservation_id
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(attempt_booking) for _ in range(2)]
            outcomes = [future.result(timeout=30) for future in futures]

        assert sum(isinstance(outcome, int) for outcome in outcomes) == 1
        assert outcomes.count("conflict") == 1

        # Verify committed state through a third, independent MariaDB session.
        verification_connection = get_test_connection()
        try:
            placeholders = ", ".join(["%s"] * len(created_ids))
            with verification_connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS reservation_count
                    FROM reservations
                    WHERE id IN ({placeholders})
                      AND cottage_id = %s
                      AND status IN ('PENDING', 'CONFIRMED')
                      AND check_in < %s
                      AND check_out > %s
                    """,
                    (*created_ids, cottage_id, check_out, check_in),
                )
                reservation_count = cursor.fetchone()["reservation_count"]
            assert reservation_count == 1
        finally:
            verification_connection.close()
    finally:
        # IDs are recorded immediately after INSERT, so a later exception
        # cannot make a committed test row invisible to cleanup.
        with created_ids_lock:
            ids_to_delete = list(created_ids)
        if ids_to_delete:
            cleanup_connection = get_test_connection()
            try:
                with cleanup_connection.cursor() as cursor:
                    placeholders = ", ".join(["%s"] * len(ids_to_delete))
                    cursor.execute(
                        f"DELETE FROM reservations WHERE id IN ({placeholders})",
                        ids_to_delete,
                    )
                cleanup_connection.commit()
            except BaseException:
                cleanup_connection.rollback()
                raise
            finally:
                cleanup_connection.close()
