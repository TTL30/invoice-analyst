"""FastAPI entrypoint for the Invoice Analyst backend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .middleware import APIKeyMiddleware
from .routers import dashboard, extraction, invoices, products


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Invoice Analyst API", version="1.0.0")
    allow_origins = settings.cors_origins or ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(APIKeyMiddleware)

    app.include_router(extraction.router, prefix="/api")
    app.include_router(invoices.router, prefix="/api")
    app.include_router(products.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")

    @app.get("/", tags=["info"])
    def root() -> dict[str, str]:
        return {"message": "Invoice Analyst API", "version": "1.0.0", "docs": "/docs"}

    @app.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/debug/cors", tags=["debug"])
    def debug_cors():
        return {
            "allow_origins": allow_origins,
            "allow_credentials": allow_credentials,
            "cors_env_var": settings.cors_origins,
        }

    return app


app = create_app()
