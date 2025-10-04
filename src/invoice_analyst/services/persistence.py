"""Persistence layer for invoices and related entities."""

from __future__ import annotations

from typing import Optional

from supabase import Client

from invoice_analyst.domain.models import Article, InvoiceSavePayload
from invoice_analyst.services.storage import StoredFile, store_pdf


def _merge_duplicate_articles(articles: list[Article]) -> list[Article]:
    """Merge articles with the same product identifier (reference or designation).

    Numeric fields (quantity, packaging, total) are summed.
    Non-numeric fields use the first non-None value.
    """
    article_map: dict[str, Article] = {}

    for article in articles:
        key = article.reference or article.designation
        if not key:
            continue

        if key not in article_map:
            article_map[key] = article.model_copy(deep=True)
        else:
            existing = article_map[key]
            # Sum numeric fields
            if article.quantity is not None:
                existing.quantity = (existing.quantity or 0) + article.quantity
            if article.packaging is not None:
                existing.packaging = (existing.packaging or 0) + article.packaging
            if article.total is not None:
                existing.total = (existing.total or 0) + article.total
            # Keep first non-None for other fields
            existing.unit = existing.unit or article.unit
            existing.unit_price = existing.unit_price or article.unit_price
            existing.poids_volume = existing.poids_volume or article.poids_volume
            existing.brand = existing.brand or article.brand
            existing.category = existing.category or article.category

    return list(article_map.values())


def _get_single_id(query_result) -> Optional[int]:
    data = getattr(query_result, "data", None) or []
    if not data:
        return None
    return data[0].get("id")


def _get_or_create_supplier(
    *, supabase: Client, user_id: str, name: str, address: str | None
) -> int:
    result = (
        supabase.table("fournisseurs").select("id").eq("user_id", user_id).eq("nom", name).execute()
    )
    supplier_id = _get_single_id(result)
    if supplier_id:
        if address:
            supabase.table("fournisseurs").update({"adresse": address}).eq(
                "id", supplier_id
            ).execute()
        return supplier_id

    response = (
        supabase.table("fournisseurs")
        .insert({"user_id": user_id, "nom": name, "adresse": address or ""})
        .execute()
    )
    supplier_id = _get_single_id(response)
    if supplier_id is None:
        raise RuntimeError("Unable to create supplier")
    return supplier_id


def _get_or_create_category(
    *, supabase: Client, user_id: str, name: Optional[str]
) -> Optional[int]:
    if not name:
        return None
    result = (
        supabase.table("categories").select("id").eq("user_id", user_id).eq("nom", name).execute()
    )
    category_id = _get_single_id(result)
    if category_id:
        return category_id

    response = supabase.table("categories").insert({"user_id": user_id, "nom": name}).execute()
    return _get_single_id(response)


def _get_or_create_brand(*, supabase: Client, user_id: str, name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    result = supabase.table("marques").select("id").eq("user_id", user_id).eq("nom", name).execute()
    brand_id = _get_single_id(result)
    if brand_id:
        return brand_id

    response = supabase.table("marques").insert({"user_id": user_id, "nom": name}).execute()
    return _get_single_id(response)


def _get_or_create_product(
    *,
    supabase: Client,
    user_id: str,
    supplier_id: int,
    article: Article,
    category_id: Optional[int],
    brand_id: Optional[int],
) -> int:
    reference = article.reference or article.designation
    if not reference:
        raise ValueError("Article must contain either reference or designation")

    result = (
        supabase.table("produits")
        .select("id")
        .eq("user_id", user_id)
        .eq("reference", reference)
        .eq("fournisseur_id", supplier_id)
        .execute()
    )
    product_id = _get_single_id(result)
    if product_id:
        supabase.table("produits").update(
            {
                "designation": article.designation,
                "categorie_id": category_id,
                "marque_id": brand_id,
            }
        ).eq("id", product_id).execute()
        return product_id

    response = (
        supabase.table("produits")
        .insert(
            {
                "user_id": user_id,
                "designation": article.designation,
                "reference": reference,
                "fournisseur_id": supplier_id,
                "categorie_id": category_id,
                "marque_id": brand_id,
            }
        )
        .execute()
    )
    product_id = _get_single_id(response)
    if product_id is None:
        raise RuntimeError("Unable to create product")
    return product_id


def _upsert_invoice(
    *,
    supabase: Client,
    user_id: str,
    supplier_id: int,
    payload: InvoiceSavePayload,
    pdf_bytes: bytes,
    bucket: str,
) -> tuple[int, StoredFile]:
    result = (
        supabase.table("factures")
        .select("id")
        .eq("user_id", user_id)
        .eq("fournisseur_id", supplier_id)
        .eq("numero", payload.invoice_number)
        .execute()
    )
    invoice_id = _get_single_id(result)

    data = {
        "user_id": user_id,
        "fournisseur_id": supplier_id,
        "numero": payload.invoice_number,
        "date": payload.invoice_date.isoformat(),
        "nom_fichier": payload.filename,
        "total_ht": payload.totals.total_ht,
        "tva_amount": payload.totals.tva,
        "total_ttc": payload.totals.total_ttc,
        "nombre_colis": payload.package_count,
    }

    if invoice_id is None:
        response = supabase.table("factures").insert(data).execute()
        invoice_id = _get_single_id(response)
        if invoice_id is None:
            raise RuntimeError("Unable to create invoice")
    else:
        supabase.table("factures").update(data).eq("id", invoice_id).execute()

    object_name = f"{user_id}/{invoice_id}_{payload.filename}"
    stored_file = store_pdf(
        supabase=supabase,
        bucket=bucket,
        file_path=object_name,
        content=pdf_bytes,
    )
    return invoice_id, stored_file


def persist_invoice(
    *,
    supabase: Client,
    payload: InvoiceSavePayload,
    pdf_bytes: bytes,
    bucket: str = "invoices",
) -> tuple[int, str]:
    """Persist invoice metadata and related products, returning the invoice id and storage URL."""
    supplier_id = _get_or_create_supplier(
        supabase=supabase,
        user_id=payload.user_id,
        name=payload.supplier_name,
        address=payload.supplier_address,
    )

    invoice_id, stored_file = _upsert_invoice(
        supabase=supabase,
        user_id=payload.user_id,
        supplier_id=supplier_id,
        payload=payload,
        pdf_bytes=pdf_bytes,
        bucket=bucket,
    )

    # remove existing lines for id to avoid duplicates
    supabase.table("lignes_facture").delete().eq("facture_id", invoice_id).execute()

    # Merge duplicate articles before persisting
    merged_articles = _merge_duplicate_articles(payload.articles)

    for article in merged_articles:
        category_id = _get_or_create_category(
            supabase=supabase,
            user_id=payload.user_id,
            name=article.category,
        )
        brand_id = _get_or_create_brand(
            supabase=supabase,
            user_id=payload.user_id,
            name=article.brand,
        )
        product_id = _get_or_create_product(
            supabase=supabase,
            user_id=payload.user_id,
            supplier_id=supplier_id,
            article=article,
            category_id=category_id,
            brand_id=brand_id,
        )

        supabase.table("lignes_facture").insert(
            {
                "user_id": payload.user_id,
                "facture_id": invoice_id,
                "produit_id": product_id,
                "prix_unitaire": article.unit_price,
                "collisage": article.packaging,
                "quantite": article.quantity,
                "montant": article.total,
                "unite": article.unit,
                "poids_volume": article.poids_volume,
            }
        ).execute()

    return invoice_id, stored_file.url
