"""API Key authentication middleware."""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import get_settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key for protected endpoints."""

    PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/debug/cors"}

    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate API key before processing request."""
        settings = get_settings()

        # Skip API key check for CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip API key check for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip API key check if no API key is configured (local dev)
        if not settings.api_key:
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key")

        # Validate API key
        if not api_key or api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
