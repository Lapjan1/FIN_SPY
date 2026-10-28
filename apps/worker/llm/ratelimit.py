"""
Rate limiting per config/models.yaml routing: 100 RPM global token bucket,
per-tenant fair share, exponential-backoff retries on transient failures.
Thread-safe; clock and sleep injectable for deterministic tests.
"""
import threading
import time
from typing import Callable, Dict

DEFAULT_RPM = 100
MAX_RETRIES = 3
BASE_DELAY_S = 0.2
MAX_WAIT_S = 30.0  # beyond this, callers fall back instead of hanging


class TokenBucketLimiter:
    def __init__(self, rpm: int = DEFAULT_RPM,
                 now_fn: Callable[[], float] = time.monotonic):
        self.rpm = max(1, rpm)
        self._now = now_fn
        self._lock = threading.Lock()
        self._tokens = float(self.rpm)
        self._updated = self._now()
        self._tenant_use: Dict[str, int] = {}
        self._window_start = self._now()

    def _refill(self, now: float):
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(float(self.rpm),
                               self._tokens + elapsed * self.rpm / 60.0)
            self._updated = now
        if now - self._window_start >= 60.0:
            self._window_start = now
            self._tenant_use = {}

    def acquire(self, tenant_id: str = "default") -> float:
        """Seconds to wait before a call (0 = proceed now). Records usage."""
        now = self._now()
        with self._lock:
            self._refill(now)
            # Per-tenant fair share of the current window
            active = len(self._tenant_use) + (0 if tenant_id in self._tenant_use else 1)
            fair = max(1, self.rpm // max(1, active))
            used = self._tenant_use.get(tenant_id, 0)
            if used >= fair:
                return max(0.0, 60.0 - (now - self._window_start))
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self._tenant_use[tenant_id] = used + 1
                return 0.0
            # Global bucket empty: wait for next token
            deficit = 1.0 - self._tokens
            return deficit * 60.0 / self.rpm

    def reset(self):
        with self._lock:
            self._tokens = float(self.rpm)
            self._updated = self._now()
            self._tenant_use = {}
            self._window_start = self._now()


_limiter: TokenBucketLimiter | None = None
_limiter_lock = threading.Lock()


def get_limiter() -> TokenBucketLimiter:
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                rpm = DEFAULT_RPM
                try:
                    import yaml
                    from pathlib import Path
                    cfg = yaml.safe_load(
                        Path("config/models.yaml").read_text()) or {}
                    rpm = int(cfg.get("routing", {}).get("rate_limit_rpm", rpm))
                except Exception:
                    pass
                _limiter = TokenBucketLimiter(rpm=rpm)
    return _limiter


def _retryable(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    if any(k in name for k in ("ratelimit", "timeout", "connection",
                               "internalserver", "serviceunavailable",
                               "badgateway", "gatewaytimeout")):
        return True
    msg = str(exc).lower()
    return any(k in msg for k in ("429", "rate limit", "timeout",
                                  "connection", "temporar", "503", "502",
                                  "504", "500"))


def with_retries(fn: Callable, max_retries: int = MAX_RETRIES,
                 base_delay_s: float = BASE_DELAY_S,
                 sleep_fn: Callable[[float], None] = time.sleep):
    """Call fn, retrying transient failures with exponential backoff.
    Non-retryable errors raise immediately; exhaustion re-raises the last."""
    last: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - classified below
            last = e
            if not _retryable(e) or attempt >= max_retries:
                raise
            sleep_fn(base_delay_s * (2 ** attempt))
    assert last is not None  # loop always returns or raises
    raise last
