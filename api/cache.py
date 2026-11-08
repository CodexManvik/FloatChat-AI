import re
import threading
import time
from collections import OrderedDict


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower()).rstrip("?.! ")


class TTLCache:
    def __init__(self, max_entries: int, ttl_seconds: float, clock=time.time):
        self.max_entries, self.ttl = max_entries, ttl_seconds
        self._clock = clock
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            stored_at, value = item
            if self._clock() - stored_at >= self.ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key, value) -> None:
        with self._lock:
            self._items[key] = (self._clock(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
