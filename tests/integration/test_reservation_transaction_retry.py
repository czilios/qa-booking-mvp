from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event, Lock

import pymysql
import pytest

from app.database import get_test_connection
from app.repositories.reservation_repository import ReservationRepository
from app.transaction_retry import (
    TransactionRetryExhausted,
    run_transaction_with_retry,
)


LOCK_WAIT_SECONDS = 1
SYNC_TIMEOUT_SECONDS = 15
WORKER_TIMEOUT_SECONDS = 20


def _open_test_connection():
    connection = get_test_connection()
    if connection.get_autocommit() is not False:
        connection.close()
        raise AssertionError("MariaDB retry test connection must use autocommit=False")
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


def _create_test_reservations(count=1):
    connection = _open_test_connection()
    reservation_ids = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM cottages ORDER BY id LIMIT %s", (max(2, count),))
            cottage_ids = [row["id"] for row in cursor.fetchall()]
        if len(cottage_ids) < max(2, count):
            pytest.skip("At least two cottages are required for MariaDB lock tests")

        repository = ReservationRepository(connection)
        for index in range(count):
            reservation_ids.append(
                repository.create(
                    cottage_id=cottage_ids[index],
                    source_id=1,
                    check_in=date(2099, 1, 10 + index * 5),
                    check_out=date(2099, 1, 12 + index * 5),
                    guests_count=1,
                    notes=f"retry-test-original-{index}",
                    is_test_data=True,
                )
            )
        connection.commit()
        return cottage_ids, reservation_ids
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


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


def _read_notes(reservation_ids):
    connection = _open_test_connection()
    try:
        with connection.cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(reservation_ids))
            cursor.execute(
                f"SELECT id, notes FROM reservations WHERE id IN ({placeholders}) ORDER BY id",
                tuple(reservation_ids),
            )
            return {row["id"]: row["notes"] for row in cursor.fetchall()}
    finally:
        connection.close()


def _connection_id(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT CONNECTION_ID() AS connection_id")
        return cursor.fetchone()["connection_id"]


@pytest.mark.db
def test_real_deadlock_rolls_back_and_retries_with_a_new_mariadb_session():
    cottage_ids, reservation_ids = _create_test_reservations(count=2)
    cottage_low, cottage_high = sorted(cottage_ids[:2])
    start_deadlock = Barrier(2)
    state_lock = Lock()
    attempts = {"left": 0, "right": 0}
    session_ids = {"left": [], "right": []}
    database_errors = []
    error_lock = Lock()

    def worker_operation(worker_name, reservation_id, first_cottage):
        def operation(connection):
            with state_lock:
                attempts[worker_name] += 1
                attempt_number = attempts[worker_name]
            session_ids[worker_name].append(_connection_id(connection))
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE reservations SET notes = %s WHERE id = %s",
                    (f"{worker_name}-attempt-{attempt_number}", reservation_id),
                )

            try:
                if attempt_number == 1:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT id FROM cottages WHERE id = %s FOR UPDATE",
                            (first_cottage,),
                        )
                    start_deadlock.wait(timeout=SYNC_TIMEOUT_SECONDS)
                    second_cottage = (
                        cottage_high if first_cottage == cottage_low else cottage_low
                    )
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT id FROM cottages WHERE id = %s FOR UPDATE",
                            (second_cottage,),
                        )
                else:
                    for cottage_id in (cottage_low, cottage_high):
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SELECT id FROM cottages WHERE id = %s FOR UPDATE",
                                (cottage_id,),
                            )
            except pymysql.err.OperationalError as error:
                with error_lock:
                    database_errors.append(error.args[0])
                raise

            return worker_name

        return operation

    def run_worker(worker_name, reservation_id, first_cottage):
        return run_transaction_with_retry(
            worker_operation(worker_name, reservation_id, first_cottage),
            operation_name=f"integration_deadlock_{worker_name}",
            connection_factory=_open_test_connection,
            delay=lambda _seconds: None,
            jitter=lambda low, _high: low,
        )

    executor = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [
            executor.submit(run_worker, "left", reservation_ids[0], cottage_low),
            executor.submit(run_worker, "right", reservation_ids[1], cottage_high),
        ]
        assert [future.result(timeout=WORKER_TIMEOUT_SECONDS) for future in futures] == [
            "left",
            "right",
        ]

        assert 1213 in database_errors
        retried_workers = [name for name, count in attempts.items() if count == 2]
        assert len(retried_workers) == 1
        for worker_name in retried_workers:
            assert len(set(session_ids[worker_name])) == 2

        final_notes = _read_notes(reservation_ids)
        for worker_name, reservation_id in zip(("left", "right"), reservation_ids):
            assert final_notes[reservation_id] == f"{worker_name}-attempt-{attempts[worker_name]}"
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        _cleanup_reservations(reservation_ids)


@pytest.mark.db
def test_real_lock_timeout_rolls_back_prior_write_then_retries_after_unlock():
    cottage_ids, reservation_ids = _create_test_reservations()
    cottage_id = cottage_ids[0]
    reservation_id = reservation_ids[0]
    blocker = _open_test_connection()
    with blocker.cursor() as cursor:
        cursor.execute("SELECT id FROM cottages WHERE id = %s FOR UPDATE", (cottage_id,))

    timeout_observed = Event()
    retry_delay_entered = Event()
    allow_retry = Event()
    attempts = 0
    session_ids = []
    database_errors = []

    def operation(connection):
        nonlocal attempts
        attempts += 1
        attempt_number = attempts
        session_ids.append(_connection_id(connection))
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE reservations SET notes = %s WHERE id = %s",
                (f"timeout-attempt-{attempt_number}", reservation_id),
            )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM cottages WHERE id = %s FOR UPDATE",
                    (cottage_id,),
                )
        except pymysql.err.OperationalError as error:
            database_errors.append(error.args[0])
            timeout_observed.set()
            raise
        return reservation_id

    def hold_retry_until_unlocked(_seconds):
        retry_delay_entered.set()
        if not allow_retry.wait(timeout=SYNC_TIMEOUT_SECONDS):
            raise AssertionError("Timed out waiting for the blocker transaction to end")

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        run_transaction_with_retry,
        operation,
        "integration_lock_timeout",
        connection_factory=_open_test_connection,
        delay=hold_retry_until_unlocked,
        jitter=lambda low, _high: low,
    )
    try:
        assert timeout_observed.wait(timeout=WORKER_TIMEOUT_SECONDS)
        assert retry_delay_entered.wait(timeout=SYNC_TIMEOUT_SECONDS)
        # The runner enters backoff only after rollback and close. This third
        # session verifies that the first attempt's earlier UPDATE was undone.
        assert _read_notes(reservation_ids)[reservation_id] == "retry-test-original-0"

        blocker.rollback()
        allow_retry.set()
        assert future.result(timeout=WORKER_TIMEOUT_SECONDS) == reservation_id
        assert database_errors == [1205]
        assert attempts == 2
        assert len(set(session_ids)) == 2
        assert _read_notes(reservation_ids)[reservation_id] == "timeout-attempt-2"
    finally:
        allow_retry.set()
        blocker.rollback()
        blocker.close()
        executor.shutdown(wait=True, cancel_futures=True)
        _cleanup_reservations(reservation_ids)


@pytest.mark.db
def test_three_real_lock_timeouts_exhaust_retry_and_leave_no_partial_write():
    cottage_ids, reservation_ids = _create_test_reservations()
    cottage_id = cottage_ids[0]
    reservation_id = reservation_ids[0]
    blocker = _open_test_connection()
    with blocker.cursor() as cursor:
        cursor.execute("SELECT id FROM cottages WHERE id = %s FOR UPDATE", (cottage_id,))

    attempts = 0
    session_ids = []
    database_errors = []

    def operation(connection):
        nonlocal attempts
        attempts += 1
        session_ids.append(_connection_id(connection))
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE reservations SET notes = %s WHERE id = %s",
                (f"exhausted-attempt-{attempts}", reservation_id),
            )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM cottages WHERE id = %s FOR UPDATE",
                    (cottage_id,),
                )
        except pymysql.err.OperationalError as error:
            database_errors.append(error.args[0])
            raise

    try:
        with pytest.raises(TransactionRetryExhausted) as raised:
            run_transaction_with_retry(
                operation,
                "integration_exhausted_lock_timeout",
                connection_factory=_open_test_connection,
                delay=lambda _seconds: None,
                jitter=lambda low, _high: low,
            )

        assert raised.value.error_code == 1205
        assert raised.value.attempts == 3
        assert attempts == 3
        assert database_errors == [1205, 1205, 1205]
        assert len(set(session_ids)) == 3
        assert _read_notes(reservation_ids)[reservation_id] == "retry-test-original-0"
    finally:
        blocker.rollback()
        blocker.close()
        _cleanup_reservations(reservation_ids)
