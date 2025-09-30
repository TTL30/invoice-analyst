"""FastAPI entrypoint for the Invoice Analyst backend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import dashboard, extraction, invoices, products


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Invoice Analyst API", version="1.0.0")
    allow_origins = settings.cors_origins or ["*"]
    allow_credentials = "*" not in allow_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(extraction.router, prefix="/api")
    app.include_router(invoices.router, prefix="/api")
    app.include_router(products.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")

    @app.get("/health", tags=["health"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
