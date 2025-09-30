"""Build user context from database for intelligent extraction refinement."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from supabase import Client


@dataclass
class ProductRef:
    """Reference to a product with its metadata."""

    reference: str
    designation: Optional[str]
    brand: Optional[str]
    category: Optional[str]


@dataclass
class SupplierRef:
    """Reference to a supplier."""

    id: int
    name: str
    address: Optional[str]


@dataclass
class UserContext:
    """User's historical data for context-aware extraction."""

    brands: List[str]
    categories: List[str]
    suppliers: List[SupplierRef]
    products: List[ProductRef]


def _get_unique_brands(supabase: Client, user_id: str) -> List[str]:
    """Fetch all unique brand names for this user."""
    result = (
        supabase.table("marques")
        .select("nom")
        .eq("user_id", user_id)
        .order("nom")
        .execute()
    )
    return [row["nom"] for row in result.data if row.get("nom")]


def _get_unique_categories(supabase: Client, user_id: str) -> List[str]:
    """Fetch all unique category names for this user."""
    result = (
        supabase.table("categories")
        .select("nom")
        .eq("user_id", user_id)
        .order("nom")
        .execute()
    )
    return [row["nom"] for row in result.data if row.get("nom")]


def _get_suppliers(supabase: Client, user_id: str) -> List[SupplierRef]:
    """Fetch all suppliers for this user."""
    result = (
        supabase.table("fournisseurs")
        .select("id, nom, adresse")
        .eq("user_id", user_id)
        .order("nom")
        .execute()
    )
    return [
        SupplierRef(
            id=row["id"],
            name=row["nom"],
            address=row.get("adresse"),
        )
        for row in result.data
    ]


def _get_products(
    supabase: Client, user_id: str, supplier_name: Optional[str] = None
) -> List[ProductRef]:
    """Fetch products for this user, optionally filtered by supplier."""
    query = (
        supabase.table("produits")
        .select(
            "reference, designation, marques(nom), categories(nom), fournisseurs(nom)"
        )
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(100)
    )

    # If supplier name provided, filter by supplier
    if supplier_name:
        # First get supplier id
        supplier_result = (
            supabase.table("fournisseurs")
            .select("id")
            .eq("user_id", user_id)
            .eq("nom", supplier_name)
            .execute()
        )
        if supplier_result.data:
            supplier_id = supplier_result.data[0]["id"]
            query = query.eq("fournisseur_id", supplier_id)

    result = query.execute()

    products = []
    for row in result.data:
        brand = None
        if row.get("marques"):
            brand = row["marques"].get("nom")

        category = None
        if row.get("categories"):
            category = row["categories"].get("nom")

        products.append(
            ProductRef(
                reference=row["reference"],
                designation=row.get("designation"),
                brand=brand,
                category=category,
            )
        )

    return products


def build_user_context(
    supabase: Client, user_id: str, supplier_name: Optional[str] = None
) -> UserContext:
    """
    Build comprehensive user context from database.

    Args:
        supabase: Supabase client
        user_id: User ID to fetch context for
        supplier_name: Optional supplier name to filter products

    Returns:
        UserContext with brands, categories, suppliers, and products
    """
    brands = _get_unique_brands(supabase, user_id)
    categories = _get_unique_categories(supabase, user_id)
    suppliers = _get_suppliers(supabase, user_id)
    products = _get_products(supabase, user_id, supplier_name)

    return UserContext(
        brands=brands,
        categories=categories,
        suppliers=suppliers,
        products=products,
    )