"""Generate Markdown output from table data."""

from typing import List
from invoice_analyst.extraction.pdfextract.models import TableRegion, TextBlock


def build_table(table: TableRegion, excluded_columns: List[str] = None) -> str:
    """Build Markdown table from table region.

    Args:
        table: Table region with headers and rows
        excluded_columns: List of column names to exclude from output

    Returns:
        Markdown formatted table string
    """
    lines = []
    excluded_columns = excluded_columns or []

    # Find indices of columns to keep
    included_indices = []
    included_headers = []
    for i, header in enumerate(table.headers):
        if header not in excluded_columns:
            included_indices.append(i)
            included_headers.append(header)

    # Build header row
    header_row = "| " + " | ".join(included_headers) + " |"
    lines.append(header_row)

    separator = "| " + " | ".join(["---"] * len(included_headers)) + " |"
    lines.append(separator)

    # Build data rows
    for row in table.rows:
        included_cells = []
        for i in included_indices:
            cell = row.cells[i] if i < len(row.cells) else ""
            included_cells.append(cell if cell else " ")
        row_line = "| " + " | ".join(included_cells) + " |"
        lines.append(row_line)

    return "\n".join(lines)


def generate_markdown(
    table: TableRegion, non_table_content: str = "", excluded_columns: List[str] = None
) -> str:
    """Generate complete Markdown document.

    Args:
        table: Table region to convert
        non_table_content: Non-table content as paragraphs
        excluded_columns: List of column names to exclude from output

    Returns:
        Complete Markdown string
    """
    parts = []

    if non_table_content:
        parts.append(non_table_content)
        parts.append("")

    parts.append(build_table(table, excluded_columns))

    return "\n".join(parts)


def generate_info_markdown(blocks: List[TextBlock]) -> str:
    """Generate info markdown from non-table text blocks.

    Groups blocks by page, sorts by reading order (top-to-bottom, left-to-right),
    joins blocks on same row with spaces, and adds page separators.

    Args:
        blocks: List of text blocks

    Returns:
        Markdown string with page separators in horizontal reading order
    """
    if not blocks:
        return ""

    # Group blocks by page
    pages = {}
    for block in blocks:
        if block.page not in pages:
            pages[block.page] = []
        pages[block.page].append(block)

    # Build markdown with page separators
    parts = []
    for page_num in sorted(pages.keys()):
        if parts:  # Add separator before subsequent pages
            parts.append("\n---")
            parts.append(f"# Page {page_num + 1}")
            parts.append("---\n")

        # Sort blocks in reading order and join blocks on same row
        page_blocks = pages[page_num]
        lines = join_blocks_by_row(page_blocks)

        # Add all lines from this page
        parts.extend(lines)

    return "\n".join(parts)


def join_blocks_by_row(blocks: List[TextBlock], row_tolerance: float = 5.0) -> List[str]:
    """Join text blocks on same row into single lines (horizontal reading).

    Groups blocks by y-position (rows), sorts left-to-right within each row,
    and joins them with spaces to form horizontal lines.

    Args:
        blocks: List of text blocks
        row_tolerance: Y-position tolerance for grouping blocks into same row

    Returns:
        List of text lines in reading order (one line per row)
    """
    if not blocks:
        return []

    # Group blocks by row (similar y-position)
    rows = []
    for block in blocks:
        # Find existing row within tolerance
        found_row = False
        for row in rows:
            if abs(row[0].y - block.y) < row_tolerance:
                row.append(block)
                found_row = True
                break

        if not found_row:
            rows.append([block])

    # Sort rows by y-position (top to bottom)
    rows.sort(key=lambda row: min(b.y for b in row))

    # Sort blocks within each row by x-position (left to right) and join with spaces
    lines = []
    for row in rows:
        row.sort(key=lambda b: b.x)
        line = " ".join(block.text for block in row)
        lines.append(line)

    return lines
