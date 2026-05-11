from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for provider resilience.
    
    - CLOSED: normal operation, track failures
    - OPEN: after failure_threshold consecutive failures, reject for cooldown_seconds
    - HALF_OPEN: after cooldown, allow 1 test request
    """
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    half_open_max_requests: int = 1
    
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _half_open_requests: int = field(default=0, repr=False)
    
    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_requests = 0
        return self._state
    
    def can_execute(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            return False
        # HALF_OPEN
        if self._half_open_requests < self.half_open_max_requests:
            self._half_open_requests += 1
            return True
        return False
    
    def record_success(self) -> None:
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._half_open_requests = 0
    
    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._half_open_requests = 0
    
    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_requests = 0


@dataclass
class RetryPolicy:
    """Retry policy for transient failures.
    
    Retries on: 429 (rate limit), 503 (service unavailable), TimeoutError
    Does NOT retry on: 400, 401, 403, 404 (client errors)
    """
    max_retries: int = 2
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0
    retryable_status_codes: set[int] = field(default_factory=lambda: {429, 502, 503, 504})
    
    def is_retryable(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        error_str = str(error).lower()
        
        # Timeout errors
        error_class = error.__class__.__name__.lower()
        if isinstance(error, TimeoutError) or "timeout" in error_str or "timeout" in error_class:
            return True
        if "connect" in error_class or "network" in error_str:
            return True
        
        # HTTP status code based
        for code in self.retryable_status_codes:
            if str(code) in error_str:
                return True
        
        # Rate limit specific
        if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
            return True
        
        return False
    
    def get_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        import random
        delay = self.base_delay_seconds * (2 ** attempt)
        delay = min(delay, self.max_delay_seconds)
        # Add jitter: ±25%
        jitter = delay * 0.25
        return delay + random.uniform(-jitter, jitter)


@dataclass
class ProviderHealth:
    """Tracks health state for each provider."""
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    
    def record_request(self, latency_ms: float, success: bool) -> None:
        self.total_requests += 1
        if success:
            self.total_successes += 1
            self.circuit_breaker.record_success()
        else:
            self.total_failures += 1
            self.circuit_breaker.record_failure()
        
        # Update rolling average latency
        if self.total_requests == 1:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = (self.avg_latency_ms * (self.total_requests - 1) + latency_ms) / self.total_requests
    
    def can_execute(self) -> bool:
        return self.circuit_breaker.can_execute()
    
    @property
    def state(self) -> str:
        return self.circuit_breaker.state.value
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.total_successes / self.total_requests
    
    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "success_rate": round(self.success_rate, 2),
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


class ProviderHealthRegistry:
    """Registry tracking health for all providers."""
    
    def __init__(self) -> None:
        self._health: dict[str, ProviderHealth] = {}
    
    def get(self, provider_name: str) -> ProviderHealth:
        if provider_name not in self._health:
            self._health[provider_name] = ProviderHealth()
        return self._health[provider_name]
    
    def can_execute(self, provider_name: str) -> bool:
        return self.get(provider_name).can_execute()
    
    def record(self, provider_name: str, latency_ms: float, success: bool) -> None:
        self.get(provider_name).record_request(latency_ms, success)
    
    def all_health(self) -> dict[str, dict]:
        return {name: health.to_dict() for name, health in self._health.items()}
    
    def reset(self, provider_name: str) -> None:
        if provider_name in self._health:
            self._health[provider_name].circuit_breaker.reset()
