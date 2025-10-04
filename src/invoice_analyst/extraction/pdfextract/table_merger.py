"""Merge tables across multiple pages."""

from typing import List
from invoice_analyst.extraction.pdfextract.models import TextBlock, Template, TableRegion
from invoice_analyst.extraction.pdfextract.table_detector import detect_table
from invoice_analyst.extraction.pdfextract.row_extractor import extract_rows
from invoice_analyst.extraction.pdfextract.parser import auto_detect_row_height
from invoice_analyst.extraction.pdfextract.utils import fuzzy_match_headers


def detect_all_tables(
    all_blocks: List[TextBlock], template: Template, row_height: float
) -> List[TableRegion]:
    """Detect table instances on each page.

    Args:
        all_blocks: All text blocks from PDF
        template: Template to use
        row_height: Average row height

    Returns:
        List of detected table regions
    """
    pages = set(b.page for b in all_blocks)
    tables = []

    for page in sorted(pages):
        page_blocks = [b for b in all_blocks if b.page == page]
        table = detect_table(page_blocks, template, page, row_height)

        if table:
            rows = extract_rows(page_blocks, table, row_height, template)
            table.rows = rows
            tables.append(table)

    return tables


def merge_tables(tables: List[TableRegion]) -> TableRegion:
    """Merge tables with matching headers across pages.

    Args:
        tables: List of table regions to merge

    Returns:
        Single merged table region

    Raises:
        ValueError: If no tables to merge
    """
    if not tables:
        raise ValueError("No tables to merge")

    merged = TableRegion(
        headers=tables[0].headers,
        rows=[],
        column_positions=tables[0].column_positions,
        start_y=tables[0].start_y,
        page=tables[0].page,
    )

    for table in tables:
        if fuzzy_match_headers(table.headers, merged.headers):
            merged.rows.extend(table.rows)

    return merged


def extract_and_merge_tables(all_blocks: List[TextBlock], template: Template) -> tuple:
    """Extract and merge all tables from PDF.

    Args:
        all_blocks: All text blocks from PDF
        template: Template to use

    Returns:
        Tuple of (merged_table, detected_tables)
        - merged_table: Merged table region (or None if no tables)
        - detected_tables: List of all detected table regions

    Raises:
        ValueError: If no tables found
    """
    row_height = auto_detect_row_height(all_blocks)
    tables = detect_all_tables(all_blocks, template, row_height)

    if not tables:
        raise ValueError("No tables found in PDF")

    merged_table = merge_tables(tables)
    return merged_table, tables
