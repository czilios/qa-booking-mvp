from unittest.mock import Mock

import pymysql
import pytest

from app.transaction_retry import (
    TransactionOutcomeUnknown,
    TransactionRetryExhausted,
    run_transaction_with_retry,
)


class FakeConnection:
    def __init__(self, *, commit_error=None, rollback_error=None):
        self.events = []
        self.commit_error = commit_error
        self.rollback_error = rollback_error

    def commit(self):
        self.events.append("commit")
        if self.commit_error:
            raise self.commit_error

    def rollback(self):
        self.events.append("rollback")
        if self.rollback_error:
            raise self.rollback_error

    def close(self):
        self.events.append("close")


def db_error(code, message="db failure"):
    return pymysql.err.OperationalError(code, message)


@pytest.mark.parametrize("error_code", [1213, 1205])
def test_retries_transient_error_on_new_connection_and_commits_success(error_code):
    connections = [FakeConnection(), FakeConnection()]
    created = iter(connections)
    attempts = []
    delays = []
    jitter_ranges = []

    def operation(connection):
        attempts.append(connection)
        if len(attempts) == 1:
            raise db_error(error_code)
        return "created"

    result = run_transaction_with_retry(
        operation,
        "unit_test",
        connection_factory=lambda: next(created),
        delay=delays.append,
        jitter=lambda low, high: jitter_ranges.append((low, high)) or low,
    )

    assert result == "created"
    assert attempts == connections
    assert connections[0].events == ["rollback", "close"]
    assert connections[1].events == ["commit", "close"]
    assert delays == [0.05]
    assert jitter_ranges == [(0.05, 0.1)]


def test_lock_timeout_has_full_rollback_before_retry_and_uses_second_backoff():
    connections = [FakeConnection(), FakeConnection(), FakeConnection()]
    attempts = []
    delays = []

    def operation(connection):
        attempts.append(connection)
        if len(attempts) < 3:
            raise db_error(1205)
        return 77

    result = run_transaction_with_retry(
        operation,
        "update_reservation",
        connection_factory=iter(connections).__next__,
        delay=delays.append,
        jitter=lambda low, high: low,
    )

    assert result == 77
    assert [connection.events for connection in connections] == [
        ["rollback", "close"],
        ["rollback", "close"],
        ["commit", "close"],
    ]
    assert delays == [0.05, 0.15]


def test_three_transient_failures_raise_controlled_exception_from_original():
    connections = [FakeConnection(), FakeConnection(), FakeConnection()]
    original = db_error(1213)
    delays = []

    def operation(_connection):
        raise original

    with pytest.raises(TransactionRetryExhausted) as raised:
        run_transaction_with_retry(
            operation,
            "api_create_reservation",
            connection_factory=iter(connections).__next__,
            delay=delays.append,
            jitter=lambda low, high: high,
        )

    assert raised.value.error_code == 1213
    assert raised.value.operation_name == "api_create_reservation"
    assert raised.value.attempts == 3
    assert raised.value.__cause__ is original
    assert delays == [0.1, 0.3]
    assert [connection.events for connection in connections] == [
        ["rollback", "close"],
        ["rollback", "close"],
        ["rollback", "close"],
    ]


@pytest.mark.parametrize("error", [ValueError("invalid"), db_error(1062)])
def test_non_retryable_errors_are_rolled_back_and_re_raised(error):
    connections = [FakeConnection()]
    operation = Mock(side_effect=error)

    with pytest.raises(type(error)) as raised:
        run_transaction_with_retry(
            operation,
            "unit_test",
            connection_factory=iter(connections).__next__,
            delay=Mock(),
        )

    assert raised.value is error
    assert operation.call_count == 1
    assert connections[0].events == ["rollback", "close"]


@pytest.mark.parametrize("error_code", [2006, 2013])
@pytest.mark.parametrize("failure_stage", ["operation", "commit"])
def test_lost_connection_is_unknown_outcome_and_never_retried(
    error_code, failure_stage
):
    connection = FakeConnection(
        commit_error=db_error(error_code) if failure_stage == "commit" else None
    )
    operation = Mock(
        side_effect=db_error(error_code) if failure_stage == "operation" else None,
        return_value="done",
    )
    connection_factory = Mock(return_value=connection)
    delay = Mock()

    with pytest.raises(TransactionOutcomeUnknown) as raised:
        run_transaction_with_retry(
            operation,
            "accept_inquiry",
            connection_factory=connection_factory,
            delay=delay,
        )

    assert raised.value.error_code == error_code
    assert raised.value.stage == failure_stage
    assert isinstance(raised.value.__cause__, pymysql.err.OperationalError)
    assert connection_factory.call_count == 1
    assert operation.call_count == 1
    assert delay.call_count == 0
    assert connection.events == (
        ["rollback", "close"] if failure_stage == "operation" else ["commit", "rollback", "close"]
    )


def test_rollback_failure_stops_retry_and_preserves_original_exception(caplog):
    original = db_error(1205)
    connection = FakeConnection(rollback_error=RuntimeError("rollback failed"))
    connection_factory = Mock(return_value=connection)
    operation = Mock(side_effect=original)
    delay = Mock()

    with pytest.raises(pymysql.err.OperationalError) as raised:
        run_transaction_with_retry(
            operation,
            "unit_test",
            connection_factory=connection_factory,
            delay=delay,
        )

    assert raised.value is original
    assert operation.call_count == 1
    assert connection_factory.call_count == 1
    assert delay.call_count == 0
    assert connection.events == ["rollback", "close"]
    rollback_log = next(
        record
        for record in caplog.records
        if record.message == "Database transaction cleanup failed"
    )
    assert rollback_log.stage == "rollback"
    assert rollback_log.cleanup_error_type == "RuntimeError"


def test_non_transient_commit_error_is_not_retried():
    original = db_error(1062)
    connection = FakeConnection(commit_error=original)
    delay = Mock()

    with pytest.raises(pymysql.err.OperationalError) as raised:
        run_transaction_with_retry(
            lambda _connection: "value",
            "unit_test",
            connection_factory=lambda: connection,
            delay=delay,
        )

    assert raised.value is original
    assert connection.events == ["commit", "rollback", "close"]
    delay.assert_not_called()
