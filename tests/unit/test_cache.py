from api.cache import TTLCache, normalize_question


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_ttl_expiry():
    clock = Clock()
    cache = TTLCache(max_entries=10, ttl_seconds=60, clock=clock)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}
    clock.now = 61
    assert cache.get("k") is None


def test_lru_eviction():
    cache = TTLCache(max_entries=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")
    cache.set("c", 3)
    assert cache.get("b") is None and cache.get("a") == 1 and cache.get("c") == 3


def test_normalize_question():
    assert normalize_question("  What is the  average temperature?? ") == "what is the average temperature"
