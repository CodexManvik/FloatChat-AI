"""In-memory protection for the public demo (one API instance, so memory is enough)."""

import threading
import time
from collections import defaultdict, deque


def _utc_day(timestamp: float) -> int:
    return int(timestamp // 86_400)


def client_ip(request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int | None, noun: str = "requests", clock=time.time):
        self.per_minute, self.per_day, self.noun = per_minute, per_day, noun
        self._clock = clock
        self._recent: dict[str, deque] = defaultdict(deque)
        self._daily: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, str | None]:
        now = self._clock()
        day = _utc_day(now)
        with self._lock:
            recent = self._recent[key]
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= self.per_minute:
                return False, (f"Too many {self.noun}: the demo allows {self.per_minute} {self.noun} per minute. "
                               "Please wait a moment and try again.")
            if self.per_day is not None:
                counted_day, count = self._daily.get(key, (day, 0))
                if counted_day != day:
                    count = 0
                if count >= self.per_day:
                    return False, (f"Daily limit reached: the demo allows {self.per_day} {self.noun} per day "
                                   "per visitor. Please come back tomorrow.")
                self._daily[key] = (day, count + 1)
            recent.append(now)
            if len(self._recent) > 10_000:
                self._evict(now)
            return True, None

    def _evict(self, now: float) -> None:
        for key in [k for k, q in self._recent.items() if not q or now - q[-1] >= 60]:
            del self._recent[key]


class DailyBudget:
    """Caps LLM calls per UTC day; when it runs out, answers fall back to data-only mode."""

    def __init__(self, limit: int, clock=time.time):
        self.limit = limit
        self._clock = clock
        self._day = None
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        day = _utc_day(self._clock())
        if day != self._day:
            self._day, self._used = day, 0

    def try_consume(self) -> bool:
        with self._lock:
            self._roll()
            if self._used >= self.limit:
                return False
            self._used += 1
            return True

    @property
    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return self._used >= self.limit
