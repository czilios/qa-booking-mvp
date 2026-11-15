from datetime import datetime, timedelta, timezone
from typing import Callable

from pymysql.connections import Connection


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OperatorSessionRepository:
    """Persistence for opaque operator sessions; transaction ownership stays upstream."""

    def __init__(self, connection: Connection):
        self.connection = connection

    def create(
        self,
        *,
        token_hash: str,
        csrf_token_hash: str,
        operator_id: str,
        created_at: datetime,
        last_activity_at: datetime,
        absolute_expires_at: datetime,
    ) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO operator_sessions (
                    token_hash,
                    csrf_token_hash,
                    operator_id,
                    created_at,
                    last_activity_at,
                    absolute_expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    token_hash,
                    csrf_token_hash,
                    operator_id,
                    created_at,
                    last_activity_at,
                    absolute_expires_at,
                ),
            )
            return cursor.lastrowid

    def touch_if_active(
        self,
        *,
        token_hash: str,
        clock: Callable[[], datetime] = _utc_now_naive,
        idle_timeout: timedelta = timedelta(minutes=30),
    ):
        """Refresh an active session using time sampled after obtaining its row lock."""
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, operator_id, csrf_token_hash, created_at, last_activity_at,
                       absolute_expires_at, revoked_at
                FROM operator_sessions
                WHERE token_hash = %s
                  AND revoked_at IS NULL
                FOR UPDATE
                """,
                (token_hash,),
            )
            session = cursor.fetchone()
            if session is None:
                return None

            checked_at = clock()
            if (
                session["absolute_expires_at"] <= checked_at
                or session["last_activity_at"] <= checked_at - idle_timeout
            ):
                return None

            cursor.execute(
                """
                UPDATE operator_sessions
                SET last_activity_at = GREATEST(last_activity_at, %s)
                WHERE id = %s
                  AND revoked_at IS NULL
                """,
                (checked_at, session["id"]),
            )
            session["last_activity_at"] = max(
                session["last_activity_at"], checked_at
            )
            return session

    def revoke(self, *, token_hash: str, revoked_at: datetime) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE operator_sessions
                SET revoked_at = %s
                WHERE token_hash = %s
                  AND revoked_at IS NULL
                """,
                (revoked_at, token_hash),
            )
            return cursor.rowcount == 1
