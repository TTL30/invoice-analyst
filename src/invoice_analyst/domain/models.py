"""Domain models for the Invoice Analyst backend."""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator


class SupplierInfo(BaseModel):
    """Supplier metadata extracted from an invoice."""

    name: str = Field(alias="nom", min_length=1, max_length=255)
    address: Optional[str] = Field(alias="adresse", default=None, max_length=500)

    class Config:
        populate_by_name = True


class InvoiceTotals(BaseModel):
    """Structured totals section of an invoice."""

    total_ht: float = Field(ge=0)
    tva: float = Field(ge=0)
    total_ttc: float = Field(ge=0)

    @computed_field
    @property
    def total(self) -> float:
        """Expose TTC as a convenient alias."""
        return self.total_ttc

    @field_validator("total_ttc")
    @classmethod
    def validate_total_calculation(cls, v: float, info) -> float:
        """Validate that total_ttc = total_ht + tva (within 0.01 tolerance for rounding)."""
        total_ht = info.data.get("total_ht", 0)
        tva = info.data.get("tva", 0)
        calculated_ttc = total_ht + tva
        if abs(v - calculated_ttc) > 0.01:  # Allow 1 cent tolerance for rounding
            raise ValueError(
                f"Invalid invoice totals: total_ttc ({v}) != total_ht ({total_ht}) + tva ({tva}). "
                f"Expected {calculated_ttc}"
            )
        return v


class Article(BaseModel):
    """Line item in an invoice."""

    reference: Optional[str] = Field(alias="Reference", default=None, max_length=100)
    designation: Optional[str] = Field(alias="Désignation", default=None, max_length=500)
    packaging: Optional[float] = Field(alias="Packaging", default=None, ge=0)
    quantity: Optional[float] = Field(alias="Quantité", default=None, ge=0)
    unit_price: Optional[float] = Field(alias="Prix Unitaire", default=None, ge=0)
    unit: Optional[str] = Field(alias="Unité", default=None, max_length=50)
    poids_volume: Optional[float] = Field(alias="Poids/Volume", default=None, ge=0)
    total: Optional[float] = Field(alias="Total", default=None, ge=0)
    brand: Optional[str] = Field(alias="Marque", default=None, max_length=255)
    category: Optional[str] = Field(alias="Catégorie", default=None, max_length=255)

    class Config:
        populate_by_name = True


class StructuredInvoice(BaseModel):
    """Structured output returned by the extraction pipeline."""

    invoice_number: str = Field(alias="Numéro de facture", max_length=100)
    invoice_date: date = Field(alias="Date facture")
    supplier: SupplierInfo = Field(alias="Information fournisseur")
    package_count: Optional[int] = Field(alias="Nombre de colis", default=None, ge=0)
    totals: InvoiceTotals = Field(alias="Total")
    raw_articles: object | None = Field(alias="articles", default=None)

    class Config:
        populate_by_name = True

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_flexible_date(cls, value):  # type: ignore[override]
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            text = value.strip()
            # Try multiple formats (day-first common in EU invoices)
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):  # extend as needed
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        raise ValueError("Invalid date format for invoice_date")

    @field_validator("invoice_date", mode="after")
    @classmethod
    def validate_not_future(cls, value: date) -> date:
        """Prevent invoice dates in the future."""
        if value > date.today():
            raise ValueError(f"Invoice date cannot be in the future: {value}")
        return value


class ExtractionResult(BaseModel):
    """Returned payload for an extraction request."""

    structured: StructuredInvoice
    articles: List[Article]
    annotated_pdf_base64: Optional[str] = None


class ExtractionRequest(BaseModel):
    """Metadata required to launch extraction for a PDF."""

    user_id: str


class InvoiceSavePayload(BaseModel):
    """Payload for persisting an extracted invoice."""

    user_id: str
    invoice_number: str = Field(max_length=100)
    invoice_date: date
    supplier_name: str = Field(max_length=255)
    supplier_address: Optional[str] = Field(default=None, max_length=500)
    filename: str = Field(max_length=255)
    totals: InvoiceTotals
    package_count: Optional[int] = None
    articles: List[Article]


class InvoiceDeletePayload(BaseModel):
    user_id: str
    invoice_ids: List[int]


class BulkDownloadRequest(BaseModel):
    user_id: str
    invoice_ids: List[int]

    @field_validator("invoice_ids")
    def non_empty(cls, value: Iterable[int]) -> List[int]:
        values = list(value)
        if not values:
            raise ValueError("invoice_ids must not be empty")
        return values
