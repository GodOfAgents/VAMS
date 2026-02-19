import time
from typing import Dict, Optional
import logging

logger = logging.getLogger("VAMS-RateLimit")

class RateLimiter:
    """
    Simple in-memory Token Bucket Rate Limiter.
    For production, replace with Redis-backed implementation.
    """
    
    def __init__(self, default_limit: int = 60, window_sec: int = 60):
        self.default_limit = default_limit
        self.window_sec = window_sec
        self.buckets: Dict[str, Dict[str, float]] = {}
        
    def is_allowed(self, key: str, limit: Optional[int] = None) -> bool:
        """
        Check if request is allowed for the given key (IP or AgentID).
        Returns True if allowed, False if limited.
        """
        now = time.time()
        limit = limit or self.default_limit
        
        if key not in self.buckets:
            self.buckets[key] = {"tokens": limit, "last_refill": now}
        
        bucket = self.buckets[key]
        
        # Refill tokens
        elapsed = now - bucket["last_refill"]
        refill_amount = elapsed * (limit / self.window_sec)
        bucket["tokens"] = min(limit, bucket["tokens"] + refill_amount)
        bucket["last_refill"] = now
        
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        else:
            logger.warning(f"Rate limit exceeded for {key}")
            return False
            
    def cleanup(self):
        """Remove old buckets to prevent memory leak."""
        now = time.time()
        keys_to_remove = []
        for key, bucket in self.buckets.items():
            if now - bucket["last_refill"] > self.window_sec * 2:
                keys_to_remove.append(key)
        
        for k in keys_to_remove:
            del self.buckets[k]
