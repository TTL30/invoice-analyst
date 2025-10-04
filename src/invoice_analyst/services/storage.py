"""Storage helpers for interacting with Supabase buckets."""

from __future__ import annotations

from dataclasses import dataclass

from urllib.parse import urljoin

from supabase import Client

DEFAULT_SIGNED_URL_TTL = 60 * 60


@dataclass(slots=True)
class StoredFile:
    path: str
    url: str


def store_pdf(
    *,
    supabase: Client,
    bucket: str,
    file_path: str,
    content: bytes,
    content_type: str = "application/pdf",
    signed_url_ttl: int = DEFAULT_SIGNED_URL_TTL,
) -> StoredFile:
    """Upload the PDF if needed and return storage metadata."""
    folder = "/".join(file_path.split("/")[:-1])
    files = supabase.storage.from_(bucket).list(folder)
    existing_names = {file.get("name") for file in files if file.get("name")}
    base_name = file_path.split("/")[-1]

    if base_name not in existing_names:
        supabase.storage.from_(bucket).upload(
            path=file_path,
            file=content,
            file_options={"content_type": content_type},
        )

    url_data = supabase.storage.from_(bucket).create_signed_url(file_path, signed_url_ttl)
    url = url_data.get("signedURL") or url_data.get("url")
    if not url:
        raise RuntimeError(f"Unable to create signed URL for {file_path}")
    if not url.lower().startswith(("http://", "https://")):
        base_url = getattr(supabase, "storage_url", None) or getattr(supabase.storage, "url", None)
        if base_url:
            url = urljoin(base_url if base_url.endswith("/") else f"{base_url}/", url.lstrip("/"))
        else:
            # Fallback: join with Supabase REST url (strip trailing /rest/v1)
            rest_url = getattr(supabase, "rest_url", "")
            if rest_url:
                storage_base = rest_url.split("/rest/v1")[0] + "/storage/v1/"
                url = urljoin(storage_base, url.lstrip("/"))
    return StoredFile(path=file_path, url=url)


def delete_pdf(*, supabase: Client, bucket: str, file_path: str) -> None:
    supabase.storage.from_(bucket).remove([file_path])


def create_signed_url(
    *, supabase: Client, bucket: str, file_path: str, ttl: int = DEFAULT_SIGNED_URL_TTL
) -> str:
    url_data = supabase.storage.from_(bucket).create_signed_url(file_path, ttl)
    url = url_data.get("signedURL") or url_data.get("url")
    if not url:
        raise RuntimeError(f"Unable to create signed URL for {file_path}")
    return url
