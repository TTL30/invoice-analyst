"""Extraction routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from invoice_analyst.domain.models import Article, ExtractionRequest
from invoice_analyst.services.extraction import extract_invoice

from ..config import Settings, get_mistral, get_settings, get_supabase

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("", summary="Run invoice extraction")
async def run_extraction(
    *,
    user_id: str = Form(...),
    confirmation_row: str = Form(...),
    file: UploadFile = File(...),
    supabase=Depends(get_supabase),
    mistral=Depends(get_mistral),
    settings: Settings = Depends(get_settings),
):
    try:
        confirmation_payload = json.loads(confirmation_row)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid confirmation_row JSON") from exc

    confirmation_article = Article.model_validate(
        confirmation_payload, from_attributes=True
    )
    request = ExtractionRequest(user_id=user_id, confirmation_row=confirmation_article)

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    categories_response = (
        supabase.table("categories")
        .select("nom")
        .eq("user_id", user_id)
        .execute()
    )
    categories = [row.get("nom") for row in categories_response.data or []]

    result = extract_invoice(
        supabase=supabase,
        mistral=mistral,
        request=request,
        pdf_content=pdf_bytes,
        filename=file.filename or "invoice.pdf",
        categories=categories,
        temp_bucket=settings.invoices_bucket,
    )

    return {
        "structured": result.structured.model_dump(by_alias=True),
        "articles": [article.model_dump(by_alias=True) for article in result.articles],
        "annotatedPdfBase64": result.annotated_pdf_base64,
        "fileName": file.filename or "invoice.pdf",
        "refinementSummary": result.refinement_summary,
    }
