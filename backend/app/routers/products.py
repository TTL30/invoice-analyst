"""Product management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_supabase
from ..schemas.product import (
    ProductDeleteRequest,
    ProductUpdateRequest,
    ProductUpdateResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.delete("/{product_id}", summary="Delete a product")
async def delete_product(
    product_id: int,
    payload: ProductDeleteRequest,
    supabase=Depends(get_supabase),
):
    """Delete a product if it belongs to the user and has no invoice lines."""
    # Verify product belongs to user
    product = (
        supabase.table("produits")
        .select("id")
        .eq("id", product_id)
        .eq("user_id", payload.userId)
        .execute()
    )

    if not product.data:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if product is used in any invoice lines
    lines = (
        supabase.table("lignes_facture")
        .select("id")
        .eq("produit_id", product_id)
        .limit(1)
        .execute()
    )

    if lines.data:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete product that is used in invoice lines",
        )

    # Delete the product
    supabase.table("produits").delete().eq("id", product_id).execute()

    return {"deleted": True, "product_id": product_id}


@router.patch("/{product_id}", response_model=ProductUpdateResponse, summary="Update a product")
async def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    supabase=Depends(get_supabase),
):
    """Update product fields."""
    # Verify product belongs to user
    product = (
        supabase.table("produits")
        .select("id")
        .eq("id", product_id)
        .eq("user_id", payload.userId)
        .execute()
    )

    if not product.data:
        raise HTTPException(status_code=404, detail="Product not found")

    # Build update dict with only provided fields
    updates = {}
    if payload.reference is not None:
        updates["reference"] = payload.reference
    if payload.designation is not None:
        updates["designation"] = payload.designation
    if payload.fournisseur_id is not None:
        updates["fournisseur_id"] = payload.fournisseur_id
    if payload.marque_id is not None:
        updates["marque_id"] = payload.marque_id
    if payload.categorie_id is not None:
        updates["categorie_id"] = payload.categorie_id

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Update the product
    supabase.table("produits").update(updates).eq("id", product_id).execute()

    return ProductUpdateResponse(success=True, product_id=product_id)