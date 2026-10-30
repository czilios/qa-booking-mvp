from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock


class SlidingWindowRateLimiter:
    def __init__(self):
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= limit:
                return False

            requests.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()
