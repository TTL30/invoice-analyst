"""Supabase client helpers."""

from __future__ import annotations

from functools import lru_cache
from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase_client(url: str, key: str) -> Client:
    """Return a cached Supabase client for the given credentials."""
    return create_client(url, key)
