from datetime import datetime, timedelta, timezone

from app.rate_limiter import SlidingWindowRateLimiter


def test_sliding_window_limiter_expires_old_attempts():
    limiter = SlidingWindowRateLimiter()
    start = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

    assert limiter.allow("ip-a", limit=2, window_seconds=60, now=start)
    assert limiter.allow(
        "ip-a",
        limit=2,
        window_seconds=60,
        now=start + timedelta(seconds=1),
    )
    assert not limiter.allow(
        "ip-a",
        limit=2,
        window_seconds=60,
        now=start + timedelta(seconds=2),
    )
    assert limiter.allow(
        "ip-a",
        limit=2,
        window_seconds=60,
        now=start + timedelta(seconds=61),
    )


def test_sliding_window_limiter_counts_clients_separately():
    limiter = SlidingWindowRateLimiter()
    now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

    assert limiter.allow("ip-a", limit=1, window_seconds=60, now=now)
    assert not limiter.allow("ip-a", limit=1, window_seconds=60, now=now)
    assert limiter.allow("ip-b", limit=1, window_seconds=60, now=now)
