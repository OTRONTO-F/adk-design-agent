"""
Rate Limiter for API calls to prevent excessive usage.

This module provides a simple rate limiting mechanism to control
the frequency of API calls, especially for expensive operations
like image generation.
"""

import time
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    A simple rate limiter that enforces a minimum time between API calls.
    
    Features:
    - Configurable cooldown period between calls
    - Tracks last call timestamp
    - Provides time remaining until next call is allowed
    - Thread-safe for single-process applications
    """
    
    def __init__(self, cooldown_seconds: float = 5.0):
        """
        Initialize the rate limiter.
        
        Args:
            cooldown_seconds: Minimum seconds between API calls (default: 5.0)
        """
        self.cooldown_seconds = cooldown_seconds
        self.last_call_time: Optional[float] = None
        self.total_calls = 0
        logger.info(f"Rate limiter initialized with {cooldown_seconds}s cooldown")
    
    def can_make_call(self) -> bool:
        """
        Check if enough time has passed since the last call.
        
        Returns:
            True if call is allowed, False if still in cooldown
        """
        if self.last_call_time is None:
            return True
        
        elapsed = time.time() - self.last_call_time
        return elapsed >= self.cooldown_seconds
    
    def time_until_next_call(self) -> float:
        """
        Calculate seconds remaining until next call is allowed.
        
        Returns:
            Seconds to wait (0 if call is allowed now)
        """
        if self.last_call_time is None:
            return 0.0
        
        elapsed = time.time() - self.last_call_time
        remaining = self.cooldown_seconds - elapsed
        return max(0.0, remaining)
    
    def wait_if_needed(self) -> float:
        """
        Block until the next call is allowed.
        
        Returns:
            Time waited in seconds
        """
        wait_time = self.time_until_next_call()
        if wait_time > 0:
            logger.info(f"Rate limit: waiting {wait_time:.1f}s before next API call")
            time.sleep(wait_time)
        return wait_time
    
    def record_call(self):
        """Record that an API call was made."""
        self.last_call_time = time.time()
        self.total_calls += 1
        logger.debug(f"API call recorded (total: {self.total_calls})")
    
    def reset(self):
        """Reset the rate limiter state."""
        self.last_call_time = None
        logger.info("Rate limiter reset")
    
    def get_stats(self) -> dict:
        """
        Get statistics about rate limiter usage.
        
        Returns:
            Dictionary with stats: total_calls, last_call_time, time_until_next
        """
        return {
            "total_calls": self.total_calls,
            "last_call_time": datetime.fromtimestamp(self.last_call_time).isoformat() if self.last_call_time else None,
            "time_until_next_call": self.time_until_next_call(),
            "cooldown_seconds": self.cooldown_seconds
        }


# Global rate limiter instance for image generation API
# Default: 5 seconds between calls to prevent API abuse
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(cooldown_seconds: float = 5.0) -> RateLimiter:
    """
    Get or create the global rate limiter instance.
    
    Args:
        cooldown_seconds: Cooldown period (only used on first call)
    
    Returns:
        Global RateLimiter instance
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(cooldown_seconds)
    return _global_rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter (useful for testing)."""
    global _global_rate_limiter
    if _global_rate_limiter:
        _global_rate_limiter.reset()


def configure_rate_limiter(cooldown_seconds: float):
    """
    Reconfigure the global rate limiter with new settings.
    
    Args:
        cooldown_seconds: New cooldown period
    """
    global _global_rate_limiter
    _global_rate_limiter = RateLimiter(cooldown_seconds)
    logger.info(f"Rate limiter reconfigured with {cooldown_seconds}s cooldown")
