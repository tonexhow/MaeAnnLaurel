"""Best-effort process-local abuse guard. NOT shared across serverless instances.

Turnstile is required in production. The guard improves behavior for repeats within
one warm function instance, but does not provide globally durable idempotency.
"""
from __future__ import annotations
import threading
import time
from collections import deque


class RateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


class IdempotencyConflict(Exception):
    pass


class MemoryGuard:
    def __init__(self, settings, clock=None):
        self.settings = settings
        self.clock = clock or time.monotonic
        self.lock = threading.Lock()
        self.requests = {}  # request_id -> (fingerprint, state, expiry)
        self.attempts = {}  # client -> timestamp deque; no message data

    def _prune(self, now):
        self.requests = {key: value for key, value in self.requests.items() if value[2] > now}
        for key in list(self.attempts):
            window = 86400 if key == "global" else self.settings.rate_window
            times = self.attempts[key]
            while times and times[0] <= now - window:
                times.popleft()
            if not times:
                del self.attempts[key]

    def lookup(self, request_id: str, fingerprint: str) -> str | None:
        with self.lock:
            now = self.clock()
            self._prune(now)
            old = self.requests.get(request_id)
            if old and old[0] != fingerprint:
                raise IdempotencyConflict()
            return old[1] if old else None

    def claim(self, request_id: str, fingerprint: str, client: str) -> str:
        with self.lock:
            now = self.clock()
            self._prune(now)
            old = self.requests.get(request_id)
            if old:
                if old[0] != fingerprint:
                    raise IdempotencyConflict()
                return old[1]
            for key, window, limit in ((client, self.settings.rate_window, self.settings.rate_limit),
                                       ("global", 86400, self.settings.global_daily_limit)):
                events = self.attempts.setdefault(key, deque())
                if len(events) >= limit:
                    raise RateLimited(max(1, int(window - (now - events[0]))))
            self.attempts[client].append(now)
            self.attempts["global"].append(now)
            self.requests[request_id] = (fingerprint, "pending", now + 3600)
            return "new"

    def finish(self, request_id: str, status: str) -> None:
        if status not in {"accepted", "uncertain", "failed"}:
            raise ValueError("Invalid delivery status")
        with self.lock:
            if request_id in self.requests:
                fingerprint, _, expiry = self.requests[request_id]
                self.requests[request_id] = (fingerprint, status, expiry)
