from api.limits import DailyBudget, RateLimiter


class Clock:
    def __init__(self, now=1_700_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_per_minute_limit_and_recovery():
    clock = Clock()
    limiter = RateLimiter(per_minute=2, per_day=None, noun="questions", clock=clock)
    assert limiter.check("a") == (True, None)
    assert limiter.check("a")[0]
    allowed, message = limiter.check("a")
    assert not allowed and "2 questions per minute" in message
    assert limiter.check("b")[0]  # other visitors are unaffected
    clock.now += 61
    assert limiter.check("a")[0]


def test_per_day_limit_resets_next_utc_day():
    clock = Clock(1_700_000_000.0)
    limiter = RateLimiter(per_minute=100, per_day=2, noun="questions", clock=clock)
    assert limiter.check("a")[0] and limiter.check("a")[0]
    allowed, message = limiter.check("a")
    assert not allowed and "2 questions per day" in message
    clock.now += 86_400
    assert limiter.check("a")[0]


def test_daily_budget():
    clock = Clock()
    budget = DailyBudget(2, clock=clock)
    assert budget.try_consume() and budget.try_consume()
    assert not budget.try_consume() and budget.exhausted
    clock.now += 86_400
    assert not budget.exhausted and budget.try_consume()
