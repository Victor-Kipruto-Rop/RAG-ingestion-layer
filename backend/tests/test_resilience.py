import pytest

from src.resilience import CircuitBreaker, CircuitOpenError, call_with_retry


def test_circuit_opens_after_threshold_and_recovers_after_timeout(monkeypatch):
    clock = {'now': 100.0}
    monkeypatch.setattr('src.resilience.time.monotonic', lambda: clock['now'])
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_seconds=10)
    def fail():
        raise ConnectionError('upstream down')
    with pytest.raises(ConnectionError):
        breaker.call(fail)
    with pytest.raises(ConnectionError):
        breaker.call(fail)
    assert breaker.state == 'OPEN'
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: 'ok')
    clock['now'] += 11
    assert breaker.call(lambda: 'ok') == 'ok'
    assert breaker.state == 'CLOSED'


def test_retry_helper_retries_only_transient_errors():
    breaker = CircuitBreaker(failure_threshold=5)
    calls = {'count': 0}
    def flaky():
        calls['count'] += 1
        if calls['count'] < 2:
            raise TimeoutError('temporary')
        return 'ok'
    assert call_with_retry(breaker, flaky) == 'ok'
    assert calls['count'] == 2
