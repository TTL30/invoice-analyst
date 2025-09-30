"""Invoice extraction orchestration."""

from __future__ import annotations

import base64
import json
from typing import Iterable, List

from supabase import Client

from invoice_analyst.logging_config import get_logger

from invoice_analyst.adapters.mistral_client import (
    MistralAdapter,
    build_structure_prompt,
)
from invoice_analyst.adapters.pdf_annotator import AnnotationRule, highlight_pdf, _find_missing_values
from invoice_analyst.adapters.refinement_client import refine_extraction
from invoice_analyst.domain.constants import ARTICLES_COLUMN_KEYS, CATEGORIES
from invoice_analyst.domain.models import (
    Article,
    ExtractionRequest,
    RefinedExtractionResult,
    StructuredInvoice,
)
from invoice_analyst.services.context_builder import build_user_context

logger = get_logger(__name__)


def _row_to_rule(article: Article) -> AnnotationRule | None:
    if not article.reference:
        return None
    data = {
        "Reference": article.reference,
        "Prix Unitaire": article.unit_price,
        "Packaging": article.packaging,
        "Quantité": article.quantity,
        "Total": article.total,
    }
    return AnnotationRule(text=str(article.reference), data={k: v for k, v in data.items() if v is not None})


def _parse_markdown_table(markdown: str) -> List[dict]:
    rows: List[dict] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("|") is False:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(ARTICLES_COLUMN_KEYS):
            continue
        rows.append(dict(zip(ARTICLES_COLUMN_KEYS, cells)))
    return rows


def _count_ocr_article_rows(ocr_markdown: str) -> int:
    """
    Count potential article rows in OCR markdown.

    This provides a rough estimate for validation by counting table-like rows.
    Not 100% accurate due to OCR noise, but useful for detecting major discrepancies.
    """
    count = 0
    in_table = False
    for line in ocr_markdown.splitlines():
        stripped = line.strip()
        # Detect table rows (lines starting with |)
        if stripped.startswith("|"):
            # Skip header separators (lines with dashes like |---|---|)
            if all(c in "|-: " for c in stripped):
                continue
            # Count as potential article row
            if in_table or stripped.count("|") >= 5:  # At least 5 columns
                count += 1
                in_table = True
        else:
            # Reset table context if we hit a non-table line
            if in_table and stripped:
                in_table = False
    return count


def _extract_ocr_table_rows(ocr_markdown: str) -> List[str]:
    """
    Extract raw table rows from OCR markdown for duplicate detection.

    Returns list of cleaned table row strings (without headers).
    """
    rows = []
    in_table = False
    seen_header = False

    for line in ocr_markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            # Skip header separator
            if all(c in "|-: " for c in stripped):
                seen_header = True
                continue

            # Skip likely header row (first row with text before separator)
            if not seen_header and not in_table:
                in_table = True
                continue

            # Collect data rows
            if stripped.count("|") >= 5:  # At least 5 columns
                rows.append(stripped)
        else:
            if in_table and stripped:
                in_table = False
                seen_header = False

    return rows


def _restore_duplicates(articles: List[Article], ocr_markdown: str) -> List[Article]:
    """
    Detect and restore duplicate consecutive articles lost during LLM structuring.

    Compares extracted articles against OCR markdown to find missing duplicates.
    """
    from collections import defaultdict

    ocr_rows = _extract_ocr_table_rows(ocr_markdown)
    if not ocr_rows or not articles:
        return articles

    # Count total occurrences of each reference in OCR
    ocr_reference_counts = defaultdict(int)
    for row in ocr_rows:
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if cells:
            reference = cells[0]
            ocr_reference_counts[reference] += 1

    # Count total occurrences in extracted articles
    extracted_counts = defaultdict(int)
    for art in articles:
        if art.reference:
            extracted_counts[art.reference] += 1

    # Find references that appear more times in OCR than in extraction
    missing_duplicates = {}
    for ref, ocr_count in ocr_reference_counts.items():
        extracted_count = extracted_counts.get(ref, 0)
        if ocr_count > extracted_count:
            missing_duplicates[ref] = ocr_count - extracted_count

    if not missing_duplicates:
        return articles

    # Restore missing duplicates by appending copies after the original
    restored_articles = []
    already_restored = set()

    for article in articles:
        restored_articles.append(article)

        if article.reference and article.reference in missing_duplicates and article.reference not in already_restored:
            # Add the missing duplicate copies
            missing_count = missing_duplicates[article.reference]
            logger.info(
                "Restoring %d duplicate(s) of article: %s",
                missing_count,
                article.reference,
            )
            for _ in range(missing_count):
                restored_articles.append(article.model_copy(deep=True))
            already_restored.add(article.reference)

    return restored_articles


def _parse_articles(raw_articles) -> List[Article]:
    if not raw_articles:
        return []

    articles: List[Article] = []
    if isinstance(raw_articles, list):
        for row in raw_articles:
            if isinstance(row, dict):
                articles.append(Article.model_validate(row, from_attributes=True))
            elif isinstance(row, (list, tuple)):
                payload = dict(zip(ARTICLES_COLUMN_KEYS, row))
                articles.append(Article.model_validate(payload, from_attributes=True))
    elif isinstance(raw_articles, str):
        for row in _parse_markdown_table(raw_articles):
            articles.append(Article.model_validate(row, from_attributes=True))
    else:
        raise TypeError("Unsupported articles payload produced by extraction")
    return articles


def _add_validation_status(article: Article, pdf_text: str) -> Article:
    """Add validation status to article based on PDF text matching."""
    # Build data dict from article fields for validation
    article_data = {}
    if article.reference:
        article_data["Reference"] = article.reference
    if article.unit_price is not None:
        article_data["Prix Unitaire"] = article.unit_price
    if article.packaging is not None:
        article_data["Packaging"] = article.packaging
    if article.quantity is not None:
        article_data["Quantité"] = article.quantity
    if article.total is not None:
        article_data["Total"] = article.total

    # Use the same logic as PDF annotator to find missing values
    missing = _find_missing_values(pdf_text, article_data)

    if missing:
        article.validation_status = "error"
        article.missing_fields = [key for key, _ in missing]
    else:
        article.validation_status = "correct"
        article.missing_fields = None

    return article


def _get_pdf_text_for_article(pdf_content: bytes, article: Article) -> str:
    """Extract the PDF text line that contains this article's reference."""
    import fitz  # type: ignore

    if not article.reference:
        return ""

    doc = fitz.open(stream=pdf_content, filetype="pdf")
    try:
        for page in doc:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    spans_sorted = sorted(line.get("spans", []), key=lambda s: s["bbox"][0])
                    if not spans_sorted:
                        continue
                    line_text = " ".join(span.get("text", "") for span in spans_sorted).strip()

                    # If this line contains the article reference, return it
                    if article.reference in line_text:
                        y0 = min(span["bbox"][1] for span in spans_sorted)
                        y1 = max(span["bbox"][3] for span in spans_sorted)
                        line_rect = fitz.Rect(0, y0, page.rect.width, y1)
                        return page.get_textbox(line_rect)
        return ""
    finally:
        doc.close()


def extract_invoice(
    *,
    supabase: Client,
    mistral: MistralAdapter,
    request: ExtractionRequest,
    pdf_content: bytes,
    filename: str,
    categories: Iterable[str] | None = None,
    temp_bucket: str = "invoices",
) -> RefinedExtractionResult:
    """Run the full extraction pipeline with intelligent refinement and return structured information."""

    # Phase 1: OCR + Structure (existing)
    aggregated_ocr = mistral.extract_markdown(file_name=filename, content=pdf_content)
    prompt = build_structure_prompt(
        aggregated_ocr=aggregated_ocr,
        example_row=request.confirmation_row.model_dump(by_alias=True, exclude_none=True),
        categories=list(categories) if categories else CATEGORIES,
    )
    structured_payload = json.loads(mistral.structure(prompt=prompt))
    structured_invoice = StructuredInvoice.model_validate(structured_payload)
    articles = _parse_articles(structured_invoice.raw_articles)

    # Validation & Restoration: Detect and restore duplicate consecutive articles
    ocr_article_count = _count_ocr_article_rows(aggregated_ocr)
    extracted_count = len(articles)
    if ocr_article_count > 0 and extracted_count < ocr_article_count:
        logger.warning(
            "Article count mismatch: OCR detected %d rows, but only %d articles were extracted. "
            "Attempting to restore lost duplicates...",
            ocr_article_count,
            extracted_count,
        )
        articles = _restore_duplicates(articles, aggregated_ocr)
        logger.info("After restoration: %d articles", len(articles))

    # Phase 2: Build user context for intelligent refinement
    supplier_name = structured_invoice.supplier.name
    user_context = build_user_context(
        supabase=supabase,
        user_id=request.user_id,
        supplier_name=supplier_name,
    )

    # Phase 3: LLM refinement with database context
    refined_result = refine_extraction(
        mistral=mistral,
        raw_structured=structured_invoice,
        raw_articles=articles,
        user_context=user_context,
    )

    # Phase 4: PDF annotation with refined articles
    annotation_rules = list(filter(None, (_row_to_rule(article) for article in refined_result.articles)))
    annotated_bytes = highlight_pdf(pdf_bytes=pdf_content, rules=annotation_rules)
    annotated_base64 = base64.b64encode(annotated_bytes).decode("utf-8")

    # Phase 5: Add validation status to each refined article
    validated_articles = []
    for article in refined_result.articles:
        pdf_text = _get_pdf_text_for_article(pdf_content, article)
        if pdf_text:
            article = _add_validation_status(article, pdf_text)
        validated_articles.append(article)

    refined_result.articles = validated_articles
    refined_result.annotated_pdf_base64 = annotated_base64

    return refined_result
