"""Invoice management routes."""

from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from invoice_analyst.domain.models import Article, InvoiceSavePayload, InvoiceTotals
from invoice_analyst.services.persistence import persist_invoice
from invoice_analyst.services.storage import delete_pdf

from ..config import Settings, get_settings, get_supabase
from ..schemas.invoice import (
    BulkDownloadRequest,
    InvoiceDeleteRequest,
    InvoiceSaveRequest,
    InvoiceSaveResponse,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceSaveResponse, summary="Persist invoice data")
async def save_invoice(
    *,
    metadata: str = Form(...),
    file: UploadFile = File(...),
    supabase=Depends(get_supabase),
    settings: Settings = Depends(get_settings),
):
    try:
        payload = InvoiceSaveRequest.model_validate_json(metadata)
    except Exception as exc:  # ValidationError
        raise HTTPException(status_code=400, detail="Payload invalide") from exc

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Le fichier PDF est vide")

    totals = InvoiceTotals.model_validate(payload.totals.model_dump())
    articles = [Article.model_validate(item, from_attributes=True) for item in payload.articles]

    domain_payload = InvoiceSavePayload(
        user_id=payload.userId,
        invoice_number=payload.invoiceNumber,
        invoice_date=payload.invoiceDate,
        supplier_name=payload.supplierName,
        supplier_address=payload.supplierAddress,
        filename=payload.filename or file.filename or "facture.pdf",
        totals=totals,
        package_count=payload.packageCount,
        articles=articles,
    )

    invoice_id, invoice_url = persist_invoice(
        supabase=supabase,
        payload=domain_payload,
        pdf_bytes=pdf_bytes,
        bucket=settings.invoices_bucket,
    )

    return InvoiceSaveResponse(invoiceUrl=invoice_url, invoiceId=invoice_id)


@router.post("/delete", summary="Delete invoices in bulk")
async def delete_invoices(
    payload: InvoiceDeleteRequest,
    supabase=Depends(get_supabase),
    settings: Settings = Depends(get_settings),
):
    ids = payload.invoiceIds
    if not ids:
        return {"deleted": 0}

    factures = (
        supabase.table("factures")
        .select("id, nom_fichier")
        .eq("user_id", payload.userId)
        .in_("id", ids)
        .execute()
    )
    data = factures.data or []
    if not data:
        return {"deleted": 0}

    storage_paths = [
        f"{payload.userId}/{item['id']}_{item['nom_fichier']}"
        for item in data
        if item.get("nom_fichier")
    ]

    supabase.table("lignes_facture").delete().in_("facture_id", ids).execute()
    supabase.table("factures").delete().in_("id", ids).execute()

    if storage_paths:
        supabase.storage.from_(settings.invoices_bucket).remove(storage_paths)

    return {"deleted": len(data)}


@router.post("/download", summary="Download invoices as a zip archive")
async def download_invoices(
    payload: BulkDownloadRequest,
    supabase=Depends(get_supabase),
    settings: Settings = Depends(get_settings),
):
    if not payload.invoiceIds:
        raise HTTPException(status_code=400, detail="invoiceIds must not be empty")

    factures = (
        supabase.table("factures")
        .select("id, nom_fichier")
        .eq("user_id", payload.userId)
        .in_("id", payload.invoiceIds)
        .execute()
    )
    data = factures.data or []
    if not data:
        raise HTTPException(status_code=404, detail="Invoices not found")

    storage_client = supabase.storage.from_(settings.invoices_bucket)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for item in data:
            file_name = item.get("nom_fichier")
            if not file_name:
                continue
            storage_path = f"{payload.userId}/{item['id']}_{file_name}"
            try:
                pdf_bytes = storage_client.download(storage_path)
            except Exception:
                continue
            zip_file.writestr(file_name, pdf_bytes)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="factures.zip"'},
    )
