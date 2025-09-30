"""API schemas for invoice endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from invoice_analyst.domain.models import InvoiceTotals


class InvoiceSaveRequest(BaseModel):
    userId: str
    invoiceNumber: str
    invoiceDate: date
    supplierName: str
    supplierAddress: Optional[str] = None
    filename: str
    totals: InvoiceTotals
    packageCount: Optional[int] = Field(default=None, ge=0)
    articles: List[Dict[str, Any]]


class InvoiceSaveResponse(BaseModel):
    invoiceUrl: str
    invoiceId: int


class InvoiceDeleteRequest(BaseModel):
    userId: str
    invoiceIds: List[int]


class BulkDownloadRequest(BaseModel):
    userId: str
    invoiceIds: List[int]
