"""Table detection and column position analysis."""

import re
from typing import List, Optional
from invoice_analyst.extraction.pdfextract.models import TextBlock, Template, TableRegion
from invoice_analyst.extraction.pdfextract.header_processor import join_multi_line_headers
from invoice_analyst.extraction.pdfextract.utils import fuzzy_match_headers


def find_start_anchor(blocks: List[TextBlock], anchor_pattern: str) -> Optional[float]:
    """Find y-position of start anchor using regex.

    Args:
        blocks: Text blocks to search
        anchor_pattern: Regex pattern for anchor

    Returns:
        Y-position of anchor or None if not found
    """
    for block in blocks:
        if re.search(anchor_pattern, block.text, re.IGNORECASE):
            return block.y

    return None


def detect_column_positions(
    blocks: List[TextBlock], start_y: float, tolerance: float = 5.0
) -> List[float]:
    """Detect column x-positions from header row.

    Args:
        blocks: All text blocks
        start_y: Y-position of header row
        tolerance: Y-position tolerance

    Returns:
        Sorted list of column x-positions
    """
    header_blocks = [b for b in blocks if abs(b.y - start_y) < tolerance]

    x_positions = sorted(set(b.x for b in header_blocks))

    if len(x_positions) == 1 and header_blocks:
        text_positions = detect_columns_from_text(header_blocks[0].text)
        if text_positions:
            base_x = x_positions[0]
            return [base_x + pos for pos in text_positions]

    return x_positions


def detect_columns_from_text(header_text: str) -> List[float]:
    """Detect column positions from single-line header text.

    For text-based PDFs where headers are in one continuous string,
    find actual character positions where headers start.

    Args:
        header_text: Full header text string

    Returns:
        List of character offsets for each column
    """
    import re

    parts = re.split(r"\s{2,}", header_text.strip())

    if len(parts) <= 1:
        return []

    positions = []
    search_pos = 0

    for part in parts:
        idx = header_text.find(part, search_pos)
        if idx >= 0:
            positions.append(float(idx))
            search_pos = idx + len(part)

    return positions


def extract_header_region(
    blocks: List[TextBlock], start_y: float, header_rows: int, row_height: float
) -> List[TextBlock]:
    """Extract text blocks in header region.

    Args:
        blocks: All text blocks
        start_y: Y-position where header starts
        header_rows: Number of header rows
        row_height: Average row height

    Returns:
        Text blocks in header region
    """
    tolerance = 5.0
    header_blocks = [b for b in blocks if abs(b.y - start_y) < tolerance]
    return header_blocks


def detect_table(
    blocks: List[TextBlock], template: Template, page: int, row_height: float
) -> Optional[TableRegion]:
    """Detect table on a page using template.

    Args:
        blocks: Text blocks for this page
        template: Template to use
        page: Page number
        row_height: Average row height

    Returns:
        TableRegion or None if no table found
    """
    start_y = find_start_anchor(blocks, template.table.start_anchor)
    if start_y is None:
        return None

    column_positions = detect_column_positions(blocks, start_y)
    if not column_positions:
        return None

    header_blocks = extract_header_region(blocks, start_y, template.table.header_rows, row_height)

    headers = join_multi_line_headers(header_blocks, column_positions, template.table.header)

    if not fuzzy_match_headers(headers, template.table.header):
        return None

    return TableRegion(
        headers=headers,
        rows=[],
        column_positions=column_positions,
        start_y=start_y + (template.table.header_rows * row_height),
        page=page,
    )
