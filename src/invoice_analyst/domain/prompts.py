"""Prompt templates for LLM-based extraction refinement."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List

from invoice_analyst.services.context_builder import UserContext


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for objects not serializable by default."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def build_refinement_prompt(
    raw_structured: Dict[str, Any],
    raw_articles: List[Dict[str, Any]],
    user_context: UserContext,
) -> str:
    """
    Build prompt for LLM refinement with user's database context.

    Args:
        raw_structured: Raw structured invoice data from initial extraction
        raw_articles: Raw article list from initial extraction
        user_context: User's existing database entities (brands, categories, products)

    Returns:
        Formatted prompt string for LLM refinement
    """
    # Format user's database entities
    brands_str = json.dumps(user_context.brands[:50], ensure_ascii=False)  # Limit to avoid token bloat
    categories_str = json.dumps(user_context.categories, ensure_ascii=False)

    # Format sample products for additional context
    products_sample = [
        {
            "reference": p.reference,
            "designation": p.designation,
            "brand": p.brand,
            "category": p.category,
        }
        for p in user_context.products[:20]  # Show top 20 recent products
    ]
    products_str = json.dumps(products_sample, indent=2, ensure_ascii=False)

    # Format raw extracted data
    raw_data_str = json.dumps(
        {"structured": raw_structured, "articles": raw_articles},
        indent=2,
        ensure_ascii=False,
        default=_json_serializer,
    )

    return f"""You are refining invoice extraction data to fix OCR errors and normalize entity names using the user's existing database.

**User's Database Entities (Historical Data)**:

Brands (top 50): {brands_str}

Categories: {categories_str}

Recent Products (showing context):
{products_str}

**Raw Extracted Data from OCR**:
{raw_data_str}

**Your Task**:
Refine the extracted data by:
1. **Fixing OCR errors**: Match extracted values to database entities when there's a clear OCR mistake
   - Example: "Coca" → "Coca-Cola" (if "Coca-Cola" exists in brands)
   - Example: "F1n" → "Flan" (if "Flan" appears in product references)
2. **Normalizing spelling/casing**: Match database formatting
   - Example: "Boisson" → "Boissons" (if "Boissons" exists in categories)
   - Example: "DANONE" → "Danone" (if "Danone" exists in brands)
3. **Matching similar entities**: Use fuzzy matching for close matches
   - Only suggest if confidence ≥ 0.85
4. **Preserving new entities**: If no close match found, mark as new_entity
   - Don't force incorrect matches

**Rules**:
- ONLY suggest matches with confidence ≥ 0.85 (high confidence)
- If confidence < 0.85, keep original and mark as new_entity
- Consider context: "Coca" near "cola" or "500ml" likely means "Coca-Cola"
- Prioritize exact matches (case-insensitive) over fuzzy matches
- For each field change, you MUST provide refinement metadata

**Output Format** (strict JSON):
{{
  "refined_articles": [
    {{
      "Reference": "...",
      "Désignation": "...",
      "Prix Unitaire": ...,
      "Packaging": ...,
      "Quantité": ...,
      "Total": ...,
      "Marque": "refined_brand_value",
      "Catégorie": "refined_category_value",

      "brand_refinement": {{
        "original_value": "original_brand_from_ocr",
        "refined_value": "refined_brand_value",
        "confidence": 0.95,
        "match_reason": "fuzzy_match_db",
        "is_new_entity": false
      }},

      "category_refinement": {{
        "original_value": "original_category_from_ocr",
        "refined_value": "refined_category_value",
        "confidence": 0.98,
        "match_reason": "exact_db_match",
        "is_new_entity": false
      }},

      "reference_refinement": {{
        "original_value": "original_ref",
        "refined_value": "corrected_ref",
        "confidence": 0.90,
        "match_reason": "ocr_correction",
        "is_new_entity": false
      }},

      "designation_refinement": {{
        "original_value": "original_designation",
        "refined_value": "corrected_designation",
        "confidence": 0.88,
        "match_reason": "ocr_correction",
        "is_new_entity": false
      }}
    }}
  ]
}}

**Match Reason Values**:
- "exact_db_match": Found exact match (case-insensitive) in database
- "fuzzy_match_db": Found similar match in database (e.g., "Coca" → "Coca-Cola")
- "ocr_correction": Fixed obvious OCR error (e.g., "F1n" → "Flan")
- "new_entity": No match found, this is a new entity

**Important**:
- If a field doesn't need refinement, you can omit the refinement metadata for that field
- Return ONLY valid JSON, no additional text or explanation
- Preserve all numeric fields (Prix Unitaire, Packaging, Quantité, Total) exactly as provided
- Focus refinement on: Marque, Catégorie, Reference, Désignation"""