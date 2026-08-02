import threading
import time


class SimpleCache:
    """Small thread-safe cache that retains expired values for fallback use."""

    def __init__(self, ttl_seconds):
        self.ttl = ttl_seconds
        self.cache = {}
        self.lock = threading.Lock()

    def get(self, key, allow_stale=False):
        with self.lock:
            item = self.cache.get(key)
            if item:
                value, timestamp = item
                if allow_stale or time.time() - timestamp < self.ttl:
                    return value
        return None

    def get_stale(self, key):
        """Return the last value even after its normal refresh TTL."""
        return self.get(key, allow_stale=True)

    def set(self, key, value):
        with self.lock:
            self.cache[key] = (value, time.time())
