from time import sleep
import pytest

class RateLimiter:
    def __init__(self, rate_limit, per_seconds):
        self.rate_limit = rate_limit
        self.per_seconds = per_seconds
        self.calls = 0
        self.start_time = None

    def wait(self):
        if self.start_time is None:
            self.start_time = time.time()
        self.calls += 1
        if self.calls > self.rate_limit:
            elapsed = time.time() - self.start_time
            if elapsed < self.per_seconds:
                sleep(self.per_seconds - elapsed)
                self.calls = 1
                self.start_time = time.time()

rate_limiter = RateLimiter(rate_limit=60, per_seconds=60)

@pytest.fixture(autouse=True)
def limit_openai_requests():
    yield
    rate_limiter.wait()
