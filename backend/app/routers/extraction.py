"""Extraction routes."""

from __future__ import annotations

import base64
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from invoice_analyst.domain.models import (
    Article,
    ExtractionResult,
    InvoiceTotals,
    StructuredInvoice,
    SupplierInfo,
)
from invoice_analyst.extraction.pipeline import process_pdf_pipeline

from ..config import Settings, get_settings, get_supabase

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("", summary="Run invoice extraction")
async def run_extraction(
    *,
    user_id: str = Form(...),
    file: UploadFile = File(...),
    supabase=Depends(get_supabase),
    settings: Settings = Depends(get_settings),
):
    # Read PDF bytes
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Validate file size (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if len(pdf_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (maximum 10MB)")

    # Validate file type (must be PDF)
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File must be a PDF document")

    # Fetch known brands and categories from database
    categories_response = (
        supabase.table("categories").select("nom").eq("user_id", user_id).execute()
    )
    categories = [row.get("nom") for row in categories_response.data or []]

    brands_response = supabase.table("marques").select("nom").eq("user_id", user_id).execute()
    brands = [row.get("nom") for row in brands_response.data or []]

    # Process PDF with new pipeline
    templates_dir = str(Path(__file__).parent.parent.parent / "templates")
    pipeline_result = process_pdf_pipeline(
        pdf_input=pdf_bytes,
        mistral_api_key=settings.mistral_api_key,
        templates_dir=templates_dir,
        known_brands=brands,
        known_categories=categories,
    )

    # Handle unknown supplier error
    if not pipeline_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=pipeline_result.get("error", "Invoice extraction failed"),
        )

    # Extract data from pipeline result
    json_data = pipeline_result["json_data"]
    annotated_pdf_bytes = pipeline_result["annotated_pdf"]
    color_mapping = pipeline_result.get("color_mapping", {})

    # Map JSON to domain models
    supplier_info = SupplierInfo(
        nom=json_data.get("supplier_name") or "",
        adresse=json_data.get("supplier_address"),
    )

    totals = InvoiceTotals(
        total_ht=json_data.get("total_without_taxes", 0.0),
        tva=json_data.get("taxes_amount", 0.0),
        total_ttc=json_data.get("total_amount", 0.0),
    )

    # Parse invoice date
    invoice_date_str = json_data.get("invoice_date")
    if invoice_date_str:
        try:
            if isinstance(invoice_date_str, str):
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                    try:
                        invoice_date = datetime.strptime(invoice_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    invoice_date = date.today()
            else:
                invoice_date = date.today()
        except Exception:
            invoice_date = date.today()
    else:
        invoice_date = date.today()

    structured = StructuredInvoice(
        **{
            "Numéro de facture": json_data.get("invoice_number") or "",
            "Date facture": invoice_date,
            "Information fournisseur": supplier_info,
            "Nombre de colis": json_data.get("total_packages"),
            "Total": totals,
            "articles": json_data.get("articles", []),
        }
    )

    # Parse articles (filter out negative values)
    articles = []
    for article_data in json_data.get("articles", []):
        # Skip articles with negative unit_price or total
        unit_price = article_data.get("Prix Unitaire")
        total = article_data.get("Total")
        if (unit_price is not None and unit_price < 0) or (total is not None and total < 0):
            continue
        articles.append(Article.model_validate(article_data, from_attributes=True))

    # Encode annotated PDF to base64
    annotated_pdf_base64 = base64.b64encode(annotated_pdf_bytes).decode("utf-8")

    # Build extraction result
    extraction_result = ExtractionResult(
        structured=structured,
        articles=articles,
        annotated_pdf_base64=annotated_pdf_base64,
    )

    return {
        "structured": extraction_result.structured.model_dump(by_alias=True),
        "articles": [article.model_dump(by_alias=True) for article in extraction_result.articles],
        "annotatedPdfBase64": extraction_result.annotated_pdf_base64,
        "fileName": file.filename or "invoice.pdf",
        "colorMapping": color_mapping,
    }
