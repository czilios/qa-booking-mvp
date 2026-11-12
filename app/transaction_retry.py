"""Run a complete database operation with bounded InnoDB retry handling."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar
from uuid import uuid4

import pymysql

from app.database import get_connection


logger = logging.getLogger(__name__)
T = TypeVar("T")

MAX_ATTEMPTS = 3
RETRYABLE_ERROR_CODES = {1205, 1213}
UNKNOWN_OUTCOME_ERROR_CODES = {2006, 2013}
BACKOFF_RANGES_SECONDS = ((0.05, 0.10), (0.15, 0.30))


class TransactionRetryExhausted(RuntimeError):
    """A transient transaction error persisted through all configured attempts."""

    def __init__(
        self,
        *,
        error_code: int,
        operation_name: str,
        attempts: int,
        correlation_id: str,
    ) -> None:
        super().__init__("The database operation could not be completed.")
        self.error_code = error_code
        self.operation_name = operation_name
        self.attempts = attempts
        self.correlation_id = correlation_id


class TransactionOutcomeUnknown(RuntimeError):
    """The connection was lost and the caller cannot know whether commit succeeded."""

    def __init__(
        self,
        *,
        error_code: int,
        operation_name: str,
        stage: str,
        correlation_id: str,
    ) -> None:
        super().__init__("The database operation outcome could not be confirmed.")
        self.error_code = error_code
        self.operation_name = operation_name
        self.stage = stage
        self.correlation_id = correlation_id


def _mariadb_error_code(error: BaseException) -> int | None:
    if not isinstance(error, pymysql.err.MySQLError) or not error.args:
        return None
    first_argument = error.args[0]
    return first_argument if isinstance(first_argument, int) else None


def _log_cleanup_failure(
    *,
    operation_name: str,
    attempt: int,
    correlation_id: str,
    stage: str,
    error: BaseException,
) -> None:
    logger.error(
        "Database transaction cleanup failed",
        extra={
            "operation_name": operation_name,
            "attempt": attempt,
            "correlation_id": correlation_id,
            "stage": stage,
            "cleanup_error_type": type(error).__name__,
        },
    )


def run_transaction_with_retry(
    operation: Callable[[object], T],
    operation_name: str,
    *,
    connection_factory: Callable[[], object] = get_connection,
    delay: Callable[[float], None] = time.sleep,
    jitter: Callable[[float, float], float] = random.uniform,
) -> T:
    """Execute and commit a whole operation, retrying only 1205 and 1213.

    Each attempt owns a fresh connection. A failed rollback prevents a retry,
    since the runner cannot confirm that the previous transaction was ended.
    """
    correlation_id = uuid4().hex

    for attempt in range(1, MAX_ATTEMPTS + 1):
        connection = connection_factory()
        stage = "operation"
        result: T | None = None
        primary_error: BaseException | None = None
        retry_code: int | None = None
        rollback_succeeded = False

        try:
            result = operation(connection)
            stage = "commit"
            connection.commit()
        except BaseException as error:
            primary_error = error
            error_code = _mariadb_error_code(error)
            logger.warning(
                "Database transaction attempt failed",
                extra={
                    "operation_name": operation_name,
                    "attempt": attempt,
                    "error_code": error_code,
                    "stage": stage,
                    "correlation_id": correlation_id,
                },
            )
            try:
                connection.rollback()
                rollback_succeeded = True
            except BaseException as rollback_error:
                _log_cleanup_failure(
                    operation_name=operation_name,
                    attempt=attempt,
                    correlation_id=correlation_id,
                    stage="rollback",
                    error=rollback_error,
                )

            if error_code in UNKNOWN_OUTCOME_ERROR_CODES:
                primary_error = TransactionOutcomeUnknown(
                    error_code=error_code,
                    operation_name=operation_name,
                    stage=stage,
                    correlation_id=correlation_id,
                )
                primary_error.__cause__ = error
            elif error_code in RETRYABLE_ERROR_CODES and rollback_succeeded:
                retry_code = error_code
        finally:
            try:
                connection.close()
            except BaseException as close_error:
                _log_cleanup_failure(
                    operation_name=operation_name,
                    attempt=attempt,
                    correlation_id=correlation_id,
                    stage="close",
                    error=close_error,
                )

        if primary_error is None:
            return result  # type: ignore[return-value]

        if retry_code is None:
            raise primary_error

        if attempt == MAX_ATTEMPTS:
            exhausted = TransactionRetryExhausted(
                error_code=retry_code,
                operation_name=operation_name,
                attempts=attempt,
                correlation_id=correlation_id,
            )
            logger.error(
                "Database transaction retry limit exhausted",
                extra={
                    "operation_name": operation_name,
                    "attempt": attempt,
                    "error_code": retry_code,
                    "stage": stage,
                    "correlation_id": correlation_id,
                },
            )
            raise exhausted from primary_error

        low, high = BACKOFF_RANGES_SECONDS[attempt - 1]
        delay(jitter(low, high))

    raise AssertionError("Unreachable transaction retry state")
