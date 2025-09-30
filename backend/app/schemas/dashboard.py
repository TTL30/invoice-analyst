"""Dashboard schema definitions."""

from __future__ import annotations

from datetime import date
from typing import List

from pydantic import BaseModel


class GlobalDashboardRequest(BaseModel):
    """Request payload for global dashboard analytics."""

    userId: str
    startDate: date
    endDate: date


class MonthlyTotal(BaseModel):
    """Monthly total spending."""

    month: str
    total: float


class InvoiceVolumeData(BaseModel):
    """Monthly invoice volume."""

    month: str
    count: int


class SupplierTotal(BaseModel):
    """Supplier spending total."""

    fournisseur: str
    total: float


class ProductQuantity(BaseModel):
    """Product quantity data."""

    designation: str
    quantite: float


class CategorySpending(BaseModel):
    """Category spending data."""

    categorie: str
    total: float


class BrandSpending(BaseModel):
    """Brand spending data."""

    marque: str
    total: float


class GlobalDashboardResponse(BaseModel):
    """Response payload for global dashboard analytics."""

    # KPIs
    totalTtc: float
    invoiceCount: int
    avgInvoiceAmount: float
    activeSuppliers: int

    # KPI period-over-period changes (%)
    totalTtcChange: float
    invoiceCountChange: float
    avgInvoiceAmountChange: float
    activeSuppliersChange: float

    # Time series
    monthlyTotals: List[MonthlyTotal]
    invoiceVolume: List[InvoiceVolumeData]

    # Supplier analytics
    supplierTotals: List[SupplierTotal]
    supplierConcentration: List[SupplierTotal]

    # Product analytics
    topProducts: List[ProductQuantity]
    categorySpending: List[CategorySpending]
    topBrands: List[BrandSpending]

    # Comparison
    momChange: float  # Month-over-month % change


class TimeDataPoint(BaseModel):
    """Time series data point."""

    date: str  # YYYY-MM format
    value: float
    unitPrice: float | None = None
    quantity: float | None = None
    amount: float | None = None


class ProductTimeSeries(BaseModel):
    """Time series data for a single product."""

    productId: int
    productName: str
    dataPoints: List[TimeDataPoint]


class ProductEvolutionRequest(BaseModel):
    """Request payload for product evolution analytics."""

    userId: str
    productIds: List[int]
    metric: str  # "unit_price", "quantity", or "amount"
    startDate: date
    endDate: date


class ProductEvolutionResponse(BaseModel):
    """Response payload for product evolution analytics."""

    series: List[ProductTimeSeries]