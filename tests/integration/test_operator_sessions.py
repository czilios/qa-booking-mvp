from datetime import datetime, timedelta

import pytest

from app.auth import (
    authenticate_operator_session,
    create_operator_session,
    revoke_operator_session,
)
from app.repositories.operator_session_repository import OperatorSessionRepository


pytestmark = pytest.mark.db


def _persist_session(connection, *, created_at):
    session = create_operator_session(now=created_at)
    OperatorSessionRepository(connection).create(
        token_hash=session.token_hash,
        csrf_token_hash=session.csrf_token_hash,
        operator_id=session.operator_id,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        absolute_expires_at=session.absolute_expires_at,
    )
    return session


def test_session_is_created_and_activity_is_refreshed(db_connection):
    created_at = datetime(2026, 1, 1, 12, 0)
    session = _persist_session(db_connection, created_at=created_at)

    active = authenticate_operator_session(
        db_connection,
        session.token,
        now=created_at + timedelta(minutes=5),
    )

    assert active is not None
    assert active["operator_id"] == "operator"
    assert active["last_activity_at"] == created_at + timedelta(minutes=5)


def test_session_expires_after_thirty_minutes_of_inactivity(db_connection):
    created_at = datetime(2026, 1, 1, 12, 0)
    session = _persist_session(db_connection, created_at=created_at)

    active = authenticate_operator_session(
        db_connection,
        session.token,
        now=created_at + timedelta(minutes=30),
    )

    assert active is None


def test_session_expires_at_twelve_hour_absolute_limit(db_connection):
    created_at = datetime(2026, 1, 1, 12, 0)
    session = _persist_session(db_connection, created_at=created_at)

    active = authenticate_operator_session(
        db_connection,
        session.token,
        now=created_at + timedelta(hours=12),
    )

    assert active is None


def test_logout_revokes_session_and_old_token_stops_working(db_connection):
    created_at = datetime(2026, 1, 1, 12, 0)
    session = _persist_session(db_connection, created_at=created_at)
    revoked = revoke_operator_session(
        db_connection,
        session.token,
        now=created_at + timedelta(minutes=1),
    )

    active = authenticate_operator_session(
        db_connection,
        session.token,
        now=created_at + timedelta(minutes=2),
    )

    assert revoked is True
    assert active is None
