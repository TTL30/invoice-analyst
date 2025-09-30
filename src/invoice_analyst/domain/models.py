"""Domain models for the Invoice Analyst backend."""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field, computed_field, field_validator


class SupplierInfo(BaseModel):
    """Supplier metadata extracted from an invoice."""

    name: str = Field(alias="nom", min_length=1)
    address: Optional[str] = Field(alias="adresse", default=None)

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


class Article(BaseModel):
    """Line item in an invoice."""

    reference: Optional[str] = Field(alias="Reference", default=None)
    designation: Optional[str] = Field(alias="Désignation", default=None)
    packaging: Optional[float] = Field(alias="Packaging", default=None, ge=0)
    quantity: Optional[float] = Field(alias="Quantité", default=None, ge=0)
    unit_price: Optional[float] = Field(alias="Prix Unitaire", default=None, ge=0)
    total: Optional[float] = Field(alias="Total", default=None, ge=0)
    brand: Optional[str] = Field(alias="Marque", default=None)
    category: Optional[str] = Field(alias="Catégorie", default=None)
    # Validation status from PDF annotation matching
    validation_status: Optional[str] = Field(alias="validationStatus", default=None)
    missing_fields: Optional[List[str]] = Field(alias="missingFields", default=None)

    class Config:
        populate_by_name = True


class StructuredInvoice(BaseModel):
    """Structured output returned by the extraction pipeline."""

    invoice_number: str = Field(alias="Numéro de facture")
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


class ExtractionResult(BaseModel):
    """Returned payload for an extraction request."""

    structured: StructuredInvoice
    articles: List[Article]
    annotated_pdf_base64: Optional[str] = None


class ExtractionRequest(BaseModel):
    """Metadata required to launch extraction for a PDF."""

    user_id: str
    confirmation_row: Article

    @field_validator("confirmation_row")
    def ensure_minimal_data(cls, value: Article) -> Article:
        """Ensure at least reference or designation is provided."""
        if not any(
            [value.reference, value.designation, value.brand, value.category]
        ):
            raise ValueError(
                "At least one of reference, designation, brand, or category must be provided"
            )
        return value


class InvoiceSavePayload(BaseModel):
    """Payload for persisting an extracted invoice."""

    user_id: str
    invoice_number: str
    invoice_date: date
    supplier_name: str
    supplier_address: Optional[str] = None
    filename: str
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


class FieldRefinement(BaseModel):
    """Refinement metadata for a single field."""

    original_value: Optional[str] = None
    refined_value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    match_reason: str  # "exact_db_match", "fuzzy_match", "ocr_correction", "new_entity"
    is_new_entity: bool


class RefinedArticle(Article):
    """Article with refinement metadata for each field."""

    brand_refinement: Optional[FieldRefinement] = None
    category_refinement: Optional[FieldRefinement] = None
    reference_refinement: Optional[FieldRefinement] = None
    designation_refinement: Optional[FieldRefinement] = None


class RefinedExtractionResult(BaseModel):
    """Enhanced extraction result with refinement metadata."""

    structured: StructuredInvoice
    articles: List[RefinedArticle]
    annotated_pdf_base64: Optional[str] = None
    refinement_summary: dict = Field(default_factory=dict)  # Stats: corrections_made, new_entities, avg_confidence
