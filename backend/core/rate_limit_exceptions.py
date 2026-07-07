"""Compatibility re-export for rate-limit worker exceptions."""

from core.worker_exceptions import RateLimitExceeded

__all__ = ["RateLimitExceeded"]
