"""Middleware package."""

from .auth import APIKeyMiddleware

__all__ = ["APIKeyMiddleware"]
