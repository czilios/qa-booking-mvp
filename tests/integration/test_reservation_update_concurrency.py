from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date
from threading import Barrier, Event, Lock, local

import pytest

from app.database import get_test_connection
from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import update_reservation


LOCK_WAIT_SECONDS = 5
SYNC_TIMEOUT_SECONDS = 15
WORKER_TIMEOUT_SECONDS = 30
SOURCE_CHANGED_ERROR = (
    "Reservation changed while waiting for cottage locks; retry the operation"
)


class SynchronizationTimeout(AssertionError):
    """A test coordination primitive timed out, not a MariaDB operation."""


def _open_test_connection():
    connection = get_test_connection()
    if connection.get_autocommit() is not False:
        connection.close()
        raise AssertionError("MariaDB test connection must use autocommit=False")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SET SESSION innodb_lock_wait_timeout = %s",
                (LOCK_WAIT_SECONDS,),
            )
    except BaseException:
        connection.close()
        raise
    return connection


def _wait_for_event(event: Event, label: str) -> None:
    if not event.wait(timeout=SYNC_TIMEOUT_SECONDS):
        raise SynchronizationTimeout(f"Timed out waiting for {label}")


def _wait_at_barrier(barrier: Barrier, label: str) -> None:
    try:
        barrier.wait(timeout=SYNC_TIMEOUT_SECONDS)
    except Exception as exc:
        # Barrier timeout/breakage is a synchronization failure. MariaDB
        # OperationalError exceptions are not caught here.
        from threading import BrokenBarrierError

        if isinstance(exc, BrokenBarrierError):
            raise SynchronizationTimeout(
                f"Timed out waiting at {label} barrier"
            ) from exc
        raise


def _create_test_reservation(connection, cottage_id, check_in, check_out):
    return ReservationRepository(connection).create(
        cottage_id=cottage_id,
        source_id=1,
        check_in=check_in,
        check_out=check_out,
        guests_count=1,
        is_test_data=True,
    )


def _require_periods_free(connection, cottage_ids, periods):
    cottage_placeholders = ", ".join(["%s"] * len(cottage_ids))
    period_predicates = " OR ".join(
        "(check_in < %s AND check_out > %s)" for _ in periods
    )
    period_parameters = tuple(
        value
        for check_in, check_out in periods
        for value in (check_out, check_in)
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id
            FROM reservations
            WHERE cottage_id IN ({cottage_placeholders})
              AND status IN ('PENDING', 'CONFIRMED')
              AND (
                status = 'CONFIRMED'
                OR expires_at IS NULL
                OR expires_at > CURRENT_TIMESTAMP
              )
              AND ({period_predicates})
            LIMIT 1
            """,
            (*cottage_ids, *period_parameters),
        )
        if cursor.fetchone() is not None:
            pytest.skip("Selected MariaDB test periods have active reservations")

        block_predicates = " OR ".join(
            "(start_date < %s AND end_date > %s)" for _ in periods
        )
        cursor.execute(
            f"""
            SELECT cottage_id
            FROM blocks
            WHERE cottage_id IN ({cottage_placeholders})
              AND ({block_predicates})
            LIMIT 1
            """,
            (*cottage_ids, *period_parameters),
        )
        if cursor.fetchone() is not None:
            pytest.skip("Selected MariaDB test periods overlap cottage blocks")


def _cleanup_reservations(reservation_ids):
    if not reservation_ids:
        return
    connection = _open_test_connection()
    try:
        with connection.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(reservation_ids))
            cursor.execute(
                f"DELETE FROM reservations WHERE id IN ({placeholders})",
                tuple(reservation_ids),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


@pytest.mark.db
def test_opposite_cottage_moves_lock_in_id_order_without_deadlock(monkeypatch):
    cottage_a, cottage_b = 1, 2
    # Separate periods let each move use the other cottage without creating
    # an availability conflict with the second test reservation.
    period_a = (date(2098, 6, 1), date(2098, 6, 4))
    period_b = (date(2098, 6, 10), date(2098, 6, 13))
    reservation_ids = []
    setup_connection = _open_test_connection()
    try:
        _require_periods_free(
            setup_connection,
            (cottage_a, cottage_b),
            (period_a, period_b),
        )
        reservation_ids.append(
            _create_test_reservation(setup_connection, cottage_a, *period_a)
        )
        reservation_ids.append(
            _create_test_reservation(setup_connection, cottage_b, *period_b)
        )
        setup_connection.commit()
    except BaseException:
        setup_connection.rollback()
        raise
    finally:
        setup_connection.close()

    first_cottage_barrier = Barrier(2)
    thread_state = local()
    acquired_cottages = {}
    acquired_cottages_lock = Lock()
    original_lock_cottage = CottageRepository.get_by_id_for_update

    def observe_cottage_lock(repository, cottage_id):
        label = thread_state.label
        if not getattr(thread_state, "reached_first_lock", False):
            thread_state.reached_first_lock = True
            _wait_at_barrier(first_cottage_barrier, "first cottage lock")
        cottage = original_lock_cottage(repository, cottage_id)
        with acquired_cottages_lock:
            acquired_cottages.setdefault(label, []).append(cottage_id)
        return cottage

    monkeypatch.setattr(
        CottageRepository,
        "get_by_id_for_update",
        observe_cottage_lock,
    )

    def run_update(label, reservation_id, target_cottage_id, period):
        connection = _open_test_connection()
        thread_state.label = label
        thread_state.reached_first_lock = False
        try:
            update_reservation(
                connection=connection,
                reservation_id=reservation_id,
                cottage_id=target_cottage_id,
                source_id=1,
                check_in=period[0],
                check_out=period[1],
                guests_count=1,
            )
            connection.commit()
            return "committed"
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    executor = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [
            executor.submit(
                run_update,
                "a_to_b",
                reservation_ids[0],
                cottage_b,
                period_a,
            ),
            executor.submit(
                run_update,
                "b_to_a",
                reservation_ids[1],
                cottage_a,
                period_b,
            ),
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=WORKER_TIMEOUT_SECONDS))
            except FutureTimeout as exc:
                raise AssertionError(
                    "Concurrent update worker exceeded its bounded timeout"
                ) from exc

        assert outcomes == ["committed", "committed"]
        assert acquired_cottages == {"a_to_b": [cottage_a, cottage_b], "b_to_a": [cottage_a, cottage_b]}

        verification_connection = _open_test_connection()
        try:
            repository = ReservationRepository(verification_connection)
            first = repository.get_by_id(reservation_ids[0])
            second = repository.get_by_id(reservation_ids[1])
            assert first["cottage_id"] == cottage_b
            assert second["cottage_id"] == cottage_a
            assert first["check_in"] == period_a[0]
            assert second["check_in"] == period_b[0]
        finally:
            verification_connection.rollback()
            verification_connection.close()
    finally:
        try:
            executor.shutdown(wait=True, cancel_futures=True)
        finally:
            _cleanup_reservations(reservation_ids)


@pytest.mark.db
def test_changed_source_cottage_rolls_back_and_releases_locks(monkeypatch):
    source_cottage, winner_cottage, stale_target_cottage = 1, 2, 3
    dates = (date(2098, 9, 1), date(2098, 9, 4))
    reservation_ids = []

    setup_connection = _open_test_connection()
    try:
        _require_periods_free(
            setup_connection,
            (source_cottage, winner_cottage, stale_target_cottage),
            (dates,),
        )
        reservation_ids.append(
            _create_test_reservation(setup_connection, source_cottage, *dates)
        )
        setup_connection.commit()
    except BaseException:
        setup_connection.rollback()
        raise
    finally:
        setup_connection.close()

    stale_read_reached_locks = Event()
    allow_stale_worker_to_lock = Event()
    thread_state = local()
    original_lock_cottage = CottageRepository.get_by_id_for_update

    def pause_stale_worker_before_cottage_lock(repository, cottage_id):
        if getattr(thread_state, "label", None) == "stale" and not getattr(
            thread_state, "paused_before_locks", False
        ):
            thread_state.paused_before_locks = True
            stale_read_reached_locks.set()
            _wait_for_event(
                allow_stale_worker_to_lock,
                "permission to acquire stale cottage locks",
            )
        return original_lock_cottage(repository, cottage_id)

    monkeypatch.setattr(
        CottageRepository,
        "get_by_id_for_update",
        pause_stale_worker_before_cottage_lock,
    )

    stale_executor = ThreadPoolExecutor(max_workers=1)
    stale_future = None
    winner_connection = None
    try:
        winner_connection = _open_test_connection()

        def run_stale_update():
            connection = _open_test_connection()
            thread_state.label = "stale"
            thread_state.paused_before_locks = False
            try:
                try:
                    update_reservation(
                        connection=connection,
                        reservation_id=reservation_ids[0],
                        cottage_id=stale_target_cottage,
                        source_id=1,
                        check_in=dates[0],
                        check_out=dates[1],
                        guests_count=1,
                    )
                except ValueError as exc:
                    connection.rollback()
                    if str(exc) != SOURCE_CHANGED_ERROR:
                        raise
                    return str(exc)

                connection.commit()
                return "unexpectedly committed"
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

        stale_future = stale_executor.submit(run_stale_update)
        _wait_for_event(stale_read_reached_locks, "stale read before cottage locks")

        update_reservation(
            connection=winner_connection,
            reservation_id=reservation_ids[0],
            cottage_id=winner_cottage,
            source_id=1,
            check_in=dates[0],
            check_out=dates[1],
            guests_count=1,
        )
        winner_connection.commit()

        allow_stale_worker_to_lock.set()
        try:
            stale_result = stale_future.result(timeout=WORKER_TIMEOUT_SECONDS)
        except FutureTimeout as exc:
            raise AssertionError(
                "Stale update worker exceeded its bounded timeout"
            ) from exc
        assert stale_result == SOURCE_CHANGED_ERROR

        # A third session must be able to lock both cottages used by the stale
        # attempt and the reservation after that worker has rolled back.
        probe_connection = _open_test_connection()
        try:
            with probe_connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM cottages WHERE id IN (%s, %s) "
                    "ORDER BY id FOR UPDATE",
                    (source_cottage, stale_target_cottage),
                )
                assert [row["id"] for row in cursor.fetchall()] == [
                    source_cottage,
                    stale_target_cottage,
                ]
                cursor.execute(
                    "SELECT id, cottage_id, check_in, check_out "
                    "FROM reservations WHERE id = %s FOR UPDATE",
                    (reservation_ids[0],),
                )
                final_reservation = cursor.fetchone()
            assert final_reservation["cottage_id"] == winner_cottage
            assert final_reservation["check_in"] == dates[0]
            assert final_reservation["check_out"] == dates[1]
            probe_connection.commit()
        except BaseException:
            probe_connection.rollback()
            raise
        finally:
            probe_connection.close()
    finally:
        allow_stale_worker_to_lock.set()
        try:
            stale_executor.shutdown(wait=True, cancel_futures=True)
        finally:
            try:
                if winner_connection is not None:
                    try:
                        winner_connection.rollback()
                    finally:
                        winner_connection.close()
            finally:
                _cleanup_reservations(reservation_ids)
