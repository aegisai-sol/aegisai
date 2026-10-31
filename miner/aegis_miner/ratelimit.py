"""Simple in-memory fixed-window rate limiter. AEGIS_RATE_LIMIT="N/SECONDS" (e.g. 30/60), per-IP. Empty/0 = off."""
import os, threading, time
class RateLimiter:
    def __init__(self, limit=0, window=60, clock=time.monotonic):
        self.limit, self.window, self.clock = int(limit), float(window), clock
        self._b, self._lock = {}, threading.Lock()
    @classmethod
    def from_env(cls, spec=None, clock=time.monotonic):
        spec = (os.environ.get("AEGIS_RATE_LIMIT", "") if spec is None else spec).strip()
        if not spec: return cls(0, 60, clock)
        n, _, w = spec.partition("/")
        return cls(int(n), float(w or 60), clock)
    def check(self, key):
        """Returns (allowed, retry_after_seconds)."""
        if self.limit <= 0: return True, 0
        now = self.clock()
        with self._lock:
            start, count = self._b.get(key, (now, 0))
            if now - start >= self.window: start, count = now, 0
            if count >= self.limit:
                return False, max(1, int(-(-(self.window - (now - start)) // 1)))
            self._b[key] = (start, count + 1)
            if len(self._b) > 10000:
                self._b = {k: v for k, v in self._b.items() if now - v[0] < self.window}
            return True, 0
