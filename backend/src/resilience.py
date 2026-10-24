"""Reusable circuit breaker and bounded retry helpers for external registry providers.

Not yet wired into a request path: fallback verification providers are reported as
NOT_CONFIGURED by the API. Use call_with_retry() when a provider client is added."""
import threading
import time
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

class CircuitOpenError(RuntimeError):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout_seconds=30.0):
        self.failure_threshold = max(1, int(failure_threshold))
        self.reset_timeout_seconds = max(1.0, float(reset_timeout_seconds))
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at = None
        self._probe_in_flight = False

    @property
    def state(self):
        with self._lock:
            if self._opened_at is None:
                return 'CLOSED'
            if time.monotonic() - self._opened_at >= self.reset_timeout_seconds:
                return 'HALF_OPEN'
            return 'OPEN'

    def call(self, func, *args, **kwargs):
        with self._lock:
            if self._opened_at is not None:
                if time.monotonic() - self._opened_at < self.reset_timeout_seconds:
                    raise CircuitOpenError('Provider circuit is open')
                if self._probe_in_flight:
                    raise CircuitOpenError('Provider recovery probe is already running')
                self._probe_in_flight = True
        try:
            result = func(*args, **kwargs)
        except Exception:
            with self._lock:
                self._failures += 1
                self._probe_in_flight = False
                if self._failures >= self.failure_threshold or self._opened_at is not None:
                    self._opened_at = time.monotonic()
            raise
        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._probe_in_flight = False
        return result

def call_with_retry(breaker, func, *args, **kwargs):
    """Retry only transient connection/timeout errors; never retry arbitrary business errors."""
    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(multiplier=0.2, max=2.0),
        reraise=True,
    )
    def invoke():
        return breaker.call(func, *args, **kwargs)
    return invoke()
