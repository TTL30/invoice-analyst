"""Wrapper utilities around the Mistral AI SDK."""

from __future__ import annotations

from mistralai import Mistral


class MistralAdapter:
    """Small convenience wrapper around the official Python SDK."""

    def __init__(self, api_key: str) -> None:
        self._client = Mistral(api_key=api_key)

    @property
    def client(self) -> Mistral:
        return self._client
