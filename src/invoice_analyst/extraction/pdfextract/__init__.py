"""PDF extraction package for invoice processing."""

from invoice_analyst.extraction.pdfextract.models import (
    TextBlock,
    TableRegion,
    TableRow,
    Template,
)

__all__ = [
    "TextBlock",
    "TableRegion",
    "TableRow",
    "Template",
]


def extract_text_blocks(pdf_path: str):
    """Extract text blocks from PDF (lazy import)."""
    from invoice_analyst.extraction.pdfextract.parser import extract_text_blocks as _extract

    return _extract(pdf_path)


def load_template(template_path: str):
    """Load template from YAML (lazy import)."""
    from invoice_analyst.extraction.pdfextract.detector import load_template as _load

    return _load(template_path)


def find_matching_template(blocks, template):
    """Find matching template (lazy import)."""
    from invoice_analyst.extraction.pdfextract.detector import find_matching_template as _find

    return _find(blocks, template)
