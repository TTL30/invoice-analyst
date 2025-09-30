"""LLM-based refinement adapter for intelligent extraction enhancement."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from invoice_analyst.adapters.mistral_client import MistralAdapter
from invoice_analyst.logging_config import get_logger
from invoice_analyst.domain.models import (
    Article,
    FieldRefinement,
    RefinedArticle,
    RefinedExtractionResult,
    StructuredInvoice,
)
from invoice_analyst.domain.prompts import build_refinement_prompt
from invoice_analyst.services.context_builder import UserContext

logger = get_logger(__name__)

CONFIDENCE_THRESHOLD = 0.85  # Only accept refinements with ≥85% confidence


def _apply_confidence_threshold(
    original: Optional[str], refinement: Optional[FieldRefinement]
) -> Optional[str]:
    """
    Apply confidence threshold to decide whether to accept refinement.

    Args:
        original: Original extracted value
        refinement: Refinement suggestion with confidence score

    Returns:
        Refined value if confidence ≥ threshold, otherwise original
    """
    if not refinement:
        return original

    if refinement.confidence >= CONFIDENCE_THRESHOLD:
        return refinement.refined_value
    else:
        # Low confidence: keep original
        return original


def _parse_refinement_field(field_data: Optional[Dict[str, Any]]) -> Optional[FieldRefinement]:
    """Parse refinement metadata from LLM response."""
    if not field_data:
        return None

    try:
        return FieldRefinement(
            original_value=field_data.get("original_value"),
            refined_value=field_data.get("refined_value"),
            confidence=float(field_data.get("confidence", 0.0)),
            match_reason=field_data.get("match_reason", "unknown"),
            is_new_entity=field_data.get("is_new_entity", False),
        )
    except (ValueError, TypeError, KeyError):
        return None


def _build_refined_article(
    raw_article: Article, refined_data: Dict[str, Any]
) -> RefinedArticle:
    """
    Build RefinedArticle from raw article and LLM refinement data.

    Args:
        raw_article: Original article from OCR extraction
        refined_data: Refinement data from LLM

    Returns:
        RefinedArticle with applied refinements and metadata
    """
    # Parse refinement metadata
    brand_ref = _parse_refinement_field(refined_data.get("brand_refinement"))
    category_ref = _parse_refinement_field(refined_data.get("category_refinement"))
    reference_ref = _parse_refinement_field(refined_data.get("reference_refinement"))
    designation_ref = _parse_refinement_field(
        refined_data.get("designation_refinement")
    )

    # Apply confidence thresholds
    refined_brand = _apply_confidence_threshold(raw_article.brand, brand_ref)
    refined_category = _apply_confidence_threshold(raw_article.category, category_ref)
    refined_reference = _apply_confidence_threshold(raw_article.reference, reference_ref)
    refined_designation = _apply_confidence_threshold(
        raw_article.designation, designation_ref
    )

    # Create refined article with updated values
    return RefinedArticle(
        reference=refined_reference,
        designation=refined_designation,
        packaging=raw_article.packaging,
        quantity=raw_article.quantity,
        unit_price=raw_article.unit_price,
        total=raw_article.total,
        brand=refined_brand,
        category=refined_category,
        validation_status=raw_article.validation_status,
        missing_fields=raw_article.missing_fields,
        # Refinement metadata
        brand_refinement=brand_ref,
        category_refinement=category_ref,
        reference_refinement=reference_ref,
        designation_refinement=designation_ref,
    )


def _calculate_refinement_summary(articles: List[RefinedArticle]) -> dict:
    """
    Calculate summary statistics for refinement results.

    Returns:
        Dict with stats: corrections_made, new_entities, avg_confidence
    """
    corrections_made = 0
    new_entities = 0
    confidence_scores = []

    for article in articles:
        for refinement in [
            article.brand_refinement,
            article.category_refinement,
            article.reference_refinement,
            article.designation_refinement,
        ]:
            if refinement:
                confidence_scores.append(refinement.confidence)
                if refinement.confidence >= CONFIDENCE_THRESHOLD:
                    if refinement.is_new_entity:
                        new_entities += 1
                    else:
                        corrections_made += 1

    avg_confidence = (
        sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    )

    return {
        "corrections_made": corrections_made,
        "new_entities": new_entities,
        "avg_confidence": round(avg_confidence, 3),
        "total_refinements": len(confidence_scores),
    }


def refine_extraction(
    mistral: MistralAdapter,
    raw_structured: StructuredInvoice,
    raw_articles: List[Article],
    user_context: UserContext,
) -> RefinedExtractionResult:
    """
    Execute LLM refinement to enhance extraction with database context.

    Args:
        mistral: Mistral adapter for LLM calls
        raw_structured: Raw structured invoice from initial extraction
        raw_articles: Raw articles from initial extraction
        user_context: User's database context (brands, categories, products)

    Returns:
        RefinedExtractionResult with enhanced data and metadata
    """
    # Build refinement prompt
    raw_structured_dict = raw_structured.model_dump(by_alias=True, exclude_none=True)
    raw_articles_dicts = [
        article.model_dump(by_alias=True, exclude_none=True)
        for article in raw_articles
    ]

    prompt = build_refinement_prompt(
        raw_structured=raw_structured_dict,
        raw_articles=raw_articles_dicts,
        user_context=user_context,
    )

    # Call LLM for refinement
    try:
        response_str = mistral.structure(prompt=prompt, model="pixtral-12b-latest")
        refinement_response = json.loads(response_str)
    except (json.JSONDecodeError, KeyError, Exception) as e:
        # If refinement fails, return original data without refinement
        logger.warning("Refinement failed: %s, returning original data", str(e))
        refined_articles = [
            RefinedArticle(**article.model_dump()) for article in raw_articles
        ]
        return RefinedExtractionResult(
            structured=raw_structured,
            articles=refined_articles,
            refinement_summary={
                "error": str(e),
                "corrections_made": 0,
                "new_entities": 0,
            },
        )

    # Parse refined articles
    refined_articles = []
    refined_articles_data = refinement_response.get("refined_articles", [])

    for i, raw_article in enumerate(raw_articles):
        if i < len(refined_articles_data):
            refined_data = refined_articles_data[i]
            refined_article = _build_refined_article(raw_article, refined_data)
        else:
            # No refinement data for this article, keep original
            refined_article = RefinedArticle(**raw_article.model_dump())

        refined_articles.append(refined_article)

    # Calculate summary
    summary = _calculate_refinement_summary(refined_articles)

    return RefinedExtractionResult(
        structured=raw_structured,
        articles=refined_articles,
        refinement_summary=summary,
    )