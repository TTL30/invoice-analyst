"""PDF processing pipeline for invoice extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from invoice_analyst.extraction.pdfextract.parser import extract_text_blocks
from invoice_analyst.extraction.pdfextract.detector import (
    find_matching_template_from_directory,
)
from invoice_analyst.extraction.pdfextract.table_merger import extract_and_merge_tables
from invoice_analyst.extraction.pdfextract.markdown_generator import (
    generate_markdown,
    generate_info_markdown,
)
from invoice_analyst.extraction.pdfextract.utils import (
    filter_non_table_blocks,
    deduplicate_blocks,
)
from invoice_analyst.extraction.pdfextract.mistral_extractor import MistralExtractor
from invoice_analyst.extraction.pdfextract.pdf_annotator import (
    annotate_pdf,
    generate_color_mapping,
)


def process_pdf_pipeline(
    pdf_input: bytes | str,
    mistral_api_key: str,
    templates_dir: str = "templates",
    known_brands: list[str] | None = None,
    known_categories: list[str] | None = None,
) -> dict[str, Any]:
    """Process PDF invoice with automatic supplier detection.

    Args:
        pdf_input: PDF as bytes or file path string
        mistral_api_key: Mistral API key for JSON extraction
        templates_dir: Path to templates directory (default: "templates")
        known_brands: List of known brand names from database for LLM context
        known_categories: List of known category names from database for LLM context

    Returns:
        Dictionary with processing results:
        - Success case: {"success": True, "annotated_pdf": bytes, "json_data": dict}
        - Failure case: {"success": False, "error": str, "annotated_pdf": None, "json_data": None}
    """
    try:
        # Convert path to bytes if needed
        pdf_bytes = pdf_input
        if isinstance(pdf_input, str):
            pdf_bytes = Path(pdf_input).read_bytes()

        # Extract text blocks from PDF
        blocks = extract_text_blocks(pdf_bytes)

        # Find matching template
        template = find_matching_template_from_directory(blocks, templates_dir)

        if template is None:
            return {
                "success": False,
                "error": "Invoice type not supported",
                "annotated_pdf": None,
                "json_data": None,
            }

        # Extract and merge tables
        try:
            merged_table, detected_tables = extract_and_merge_tables(blocks, template)
            excluded_columns = template.table.excluded_columns or []
            table_markdown = generate_markdown(merged_table, excluded_columns=excluded_columns)
        except ValueError:
            # No tables found - create empty table
            table_markdown = ""
            detected_tables = []

        # Filter non-table blocks
        info_blocks = filter_non_table_blocks(blocks, detected_tables)

        # Deduplicate info blocks
        deduplicated_info = deduplicate_blocks(info_blocks)

        # Generate info markdown
        info_markdown = generate_info_markdown(deduplicated_info)

        # Extract JSON using Mistral API
        extractor = MistralExtractor(mistral_api_key)
        prompt_path = Path(__file__).parent / "prompts" / "invoice_extraction.txt"
        invoice_data = extractor.extract_json(
            info_markdown,
            table_markdown,
            prompt_path,
            known_brands=known_brands or [],
            known_categories=known_categories or [],
        )

        # Generate annotated PDF
        annotated_pdf_bytes = annotate_pdf(pdf_bytes, invoice_data)

        # Generate color mapping for frontend highlighting
        color_mapping = generate_color_mapping(pdf_bytes, invoice_data)

        return {
            "success": True,
            "annotated_pdf": annotated_pdf_bytes,
            "json_data": invoice_data,
            "color_mapping": color_mapping,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "annotated_pdf": None, "json_data": None}


if __name__ == "__main__":
    process_pdf_pipeline()
