"""API schemas for product endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ProductUpdateRequest(BaseModel):
    userId: str
    reference: Optional[str] = None
    designation: Optional[str] = None
    fournisseur_id: Optional[int] = None
    marque_id: Optional[int] = None
    categorie_id: Optional[int] = None


class ProductDeleteRequest(BaseModel):
    userId: str


class ProductUpdateResponse(BaseModel):
    success: bool
    product_id: int
