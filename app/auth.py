"""Operator password and server-side session primitives.

This module intentionally does not protect application routes. Route protection
is a later implementation stage; this module provides login/session building
blocks only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Callable, Mapping

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from app.repositories.operator_session_repository import OperatorSessionRepository


OPERATOR_ID = "operator"
SESSION_COOKIE_NAME = "qa_booking_operator_session"
SESSION_IDLE_TIMEOUT = timedelta(minutes=30)
SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=12)
SESSION_TOKEN_BYTES = 32

# argon2-cffi's RFC 9106 low-memory profile (its recommended default):
# 64 MiB, three iterations, and four lanes. Reject externally configured hashes
# below the parameters used by this application's PasswordHasher.
MIN_ARGON2_MEMORY_COST = 64 * 1024
MIN_ARGON2_TIME_COST = 3
MIN_ARGON2_PARALLELISM = 4

_PASSWORD_HASH_ENV = "OPERATOR_PASSWORD_HASH"
_PASSWORD_HASHER = PasswordHasher(type=Type.ID)


class AuthConfigurationError(RuntimeError):
    """Raised when the required operator authentication config is invalid."""


@dataclass(frozen=True)
class NewOperatorSession:
    token: str
    token_hash: str
    operator_id: str
    created_at: datetime
    last_activity_at: datetime
    absolute_expires_at: datetime


def load_operator_password_hash(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return a valid Argon2id hash or fail closed; never accept a plaintext password."""
    values = os.environ if environ is None else environ
    encoded_hash = values.get(_PASSWORD_HASH_ENV, "").strip()
    if not encoded_hash:
        raise AuthConfigurationError(
            f"Required authentication setting {_PASSWORD_HASH_ENV} is missing"
        )

    try:
        parameters = extract_parameters(encoded_hash)
    except (InvalidHashError, TypeError, ValueError) as exc:
        raise AuthConfigurationError(
            f"{_PASSWORD_HASH_ENV} must contain a valid Argon2id hash"
        ) from exc

    if parameters.type is not Type.ID:
        raise AuthConfigurationError(
            f"{_PASSWORD_HASH_ENV} must use Argon2id"
        )
    if (
        parameters.memory_cost < MIN_ARGON2_MEMORY_COST
        or parameters.time_cost < MIN_ARGON2_TIME_COST
        or parameters.parallelism < MIN_ARGON2_PARALLELISM
    ):
        raise AuthConfigurationError(
            f"{_PASSWORD_HASH_ENV} does not meet the minimum Argon2id parameters"
        )
    return encoded_hash


def hash_operator_password(password: str) -> str:
    """Generate an Argon2id password hash for secure server-side configuration."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    return _PASSWORD_HASHER.hash(password)


def verify_operator_credentials(
    login: str,
    password: str,
    encoded_hash: str,
) -> bool:
    """Verify credentials with one Argon2 operation for known and unknown logins."""
    if not isinstance(password, str) or len(password.encode("utf-8")) > 1024:
        return False

    try:
        password_matches = _PASSWORD_HASHER.verify(encoded_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        return False
    return login == OPERATOR_ID and password_matches


def utc_now_naive() -> datetime:
    """Return UTC as a naive datetime for MariaDB DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_operator_session(
    *,
    now: datetime | None = None,
    token_factory=secrets.token_urlsafe,
) -> NewOperatorSession:
    created_at = now or utc_now_naive()
    token = token_factory(SESSION_TOKEN_BYTES)
    if not isinstance(token, str) or len(token) < 40:
        raise ValueError("Session token factory returned an invalid token")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return NewOperatorSession(
        token=token,
        token_hash=token_hash,
        operator_id=OPERATOR_ID,
        created_at=created_at,
        last_activity_at=created_at,
        absolute_expires_at=created_at + SESSION_ABSOLUTE_TIMEOUT,
    )


def hash_session_token(token: str | None) -> str | None:
    if not token or len(token) > 256:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_idle_cutoff(now: datetime) -> datetime:
    return now - SESSION_IDLE_TIMEOUT


def authenticate_operator_session(
    connection,
    token: str | None,
    *,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
):
    token_hash = hash_session_token(token)
    if token_hash is None:
        return None
    if clock is not None:
        post_lock_clock = clock
    elif now is not None:
        post_lock_clock = lambda: now
    else:
        post_lock_clock = utc_now_naive
    return OperatorSessionRepository(connection).touch_if_active(
        token_hash=token_hash,
        clock=post_lock_clock,
        idle_timeout=SESSION_IDLE_TIMEOUT,
    )


def revoke_operator_session(
    connection,
    token: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    token_hash = hash_session_token(token)
    if token_hash is None:
        return False
    return OperatorSessionRepository(connection).revoke(
        token_hash=token_hash,
        revoked_at=now or utc_now_naive(),
    )


def safe_login_redirect(destination: str | None) -> str:
    """Allow local absolute paths only; reject scheme-relative/open redirects."""
    if (
        not destination
        or not destination.startswith("/")
        or destination.startswith("//")
        or "\\" in destination
        or "\r" in destination
        or "\n" in destination
    ):
        return "/ui"
    return destination


def session_cookie_secure(environ: Mapping[str, str] | None = None) -> bool:
    """Require an explicit app environment; only local/test may opt out."""
    values = os.environ if environ is None else environ
    app_env = values.get("APP_ENV", "").strip().lower()
    allowed_environments = {"production", "development", "local", "test"}
    if app_env not in allowed_environments:
        raise AuthConfigurationError(
            "APP_ENV must be production, development, local, or test"
        )

    raw_value = values.get("SESSION_COOKIE_SECURE", "true").strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        if app_env not in {"local", "test"}:
            raise AuthConfigurationError(
                "SESSION_COOKIE_SECURE can be disabled only in an explicit local/test environment"
            )
        return False
    raise AuthConfigurationError("SESSION_COOKIE_SECURE must be a boolean value")


if __name__ == "__main__":
    import getpass

    first = getpass.getpass("Operator password: ")
    second = getpass.getpass("Confirm operator password: ")
    if not secrets.compare_digest(first, second):
        raise SystemExit("Passwords do not match")
    print(hash_operator_password(first))
