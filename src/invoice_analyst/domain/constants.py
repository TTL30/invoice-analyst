"""Domain-level constants for the Invoice Analyst application."""

from __future__ import annotations

from typing import Dict, List

CATEGORIES: List[str] = [
    "Matières premières",
    "Fruits, légumes, graines et fruits secs",
    "Boissons",
    "Emballages et consommables",
    "Entretien et hygiène",
    "Droguerie et divers",
    "Produits surgelés",
    "Papeterie et caisse",
    "Transport / livraison",
    "Décoration / présentation",
]

ARTICLES_COLUMNS: List[Dict[str, str]] = [
    {"key": "Reference", "label": "Reference"},
    {"key": "Désignation", "label": "Désignation"},
    {"key": "Prix Unitaire", "label": "Prix Unitaire"},
    {"key": "Packaging", "label": "Packaging"},
    {"key": "Quantité", "label": "Quantité"},
    {"key": "Total", "label": "Total"},
    {"key": "Marque", "label": "Marque"},
    {"key": "Catégorie", "label": "Catégorie"},
]

ARTICLES_COLUMN_KEYS = [column["key"] for column in ARTICLES_COLUMNS]
