"""
A minimal in-memory rate limiter.

Keyed per identifier (here, per user id), it allows up to `max_calls` within a
rolling `window_seconds`. This is deliberately simple and process-local — good
enough to protect a public demo's LLM endpoint from casual abuse.

Limitation (documented, not hidden): because state lives in memory, it resets on
restart and isn't shared across multiple server instances. A production system
behind several workers would use a shared store like Redis. That's noted as
future work.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Return True if the call is allowed, False if the limit is exceeded."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            # Drop timestamps older than the window.
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.max_calls:
                return False
            hits.append(now)
            return True


# Analysis calls are the expensive/abusable ones: cap per user.
analysis_limiter = RateLimiter(max_calls=10, window_seconds=60.0)
