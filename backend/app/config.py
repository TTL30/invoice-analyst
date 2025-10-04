"""Application configuration and dependency factories."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List
from dotenv import load_dotenv

from src.invoice_analyst.adapters.mistral_client import MistralAdapter
from src.invoice_analyst.adapters.supabase_client import get_supabase_client

load_dotenv()


@dataclass(slots=True)
class Settings:
    supabase_url: str
    supabase_key: str
    mistral_api_key: str
    api_key: str | None = None
    invoices_bucket: str = "invoices"
    cors_origins: List[str] | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        cors_raw = os.environ.get(
            "CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:3001"
        )
        cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
        if not cors_origins:
            cors_origins = ["*"]

        return Settings(
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_key=os.environ["SUPABASE_KEY"],
            mistral_api_key=os.environ["MISTRAL_API_KEY"],
            api_key=os.environ.get("API_KEY"),
            invoices_bucket=os.environ.get("SUPABASE_INVOICES_BUCKET", "invoices"),
            cors_origins=cors_origins,
        )
    except KeyError as exc:
        missing = ", ".join(sorted({key for key in exc.args}))
        raise RuntimeError(f"Missing required environment variables: {missing}") from exc


def get_supabase():
    settings = get_settings()
    return get_supabase_client(settings.supabase_url, settings.supabase_key)


def get_mistral() -> MistralAdapter:
    settings = get_settings()
    return MistralAdapter(api_key=settings.mistral_api_key)
