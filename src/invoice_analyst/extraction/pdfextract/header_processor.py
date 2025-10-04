"""Header processing for multi-line headers."""

from typing import List, Dict
from invoice_analyst.extraction.pdfextract.models import TextBlock


def group_by_column(
    blocks: List[TextBlock], tolerance: float = 10.0
) -> Dict[float, List[TextBlock]]:
    """Group text blocks by column x-position.

    Args:
        blocks: Text blocks to group
        tolerance: X-position tolerance in pixels

    Returns:
        Dictionary mapping x-position to blocks
    """
    columns = {}

    for block in blocks:
        found = False
        for col_x in list(columns.keys()):
            if abs(block.x - col_x) < tolerance:
                columns[col_x].append(block)
                found = True
                break

        if not found:
            columns[block.x] = [block]

    return columns


def detect_header_format(blocks: List[TextBlock]) -> str:
    """Detect if headers are text-based or cell-based.

    Args:
        blocks: Text blocks in header region

    Returns:
        "text-based" if all blocks at same x, "cell-based" otherwise
    """
    if not blocks:
        return "cell-based"

    first_x = blocks[0].x
    tolerance = 5.0

    all_same_x = all(abs(b.x - first_x) < tolerance for b in blocks)

    return "text-based" if all_same_x else "cell-based"


def join_multi_line_headers(
    blocks: List[TextBlock],
    column_positions: List[float],
    expected_headers: List[str],
    tolerance: float = 10.0,
) -> List[str]:
    """Join multi-line headers by column.

    Args:
        blocks: Text blocks in header region
        column_positions: Detected column x-positions
        expected_headers: Expected headers from template
        tolerance: X-position tolerance

    Returns:
        List of joined header strings
    """
    format_type = detect_header_format(blocks)

    if format_type == "text-based":
        return parse_text_based_headers(blocks, expected_headers)
    else:
        return parse_cell_based_headers(blocks, column_positions, expected_headers, tolerance)


def parse_text_based_headers(blocks: List[TextBlock], expected_headers: List[str]) -> List[str]:
    """Parse text-based headers (Metro format).

    When all headers are at same x-position, use template headers.
    Text-based PDFs have inconsistent spacing that makes parsing unreliable,
    so we rely on template and fuzzy matching.

    Args:
        blocks: Header text blocks (all at same x)
        expected_headers: Expected final headers from template

    Returns:
        List of parsed headers matching template
    """
    return expected_headers


def parse_cell_based_headers(
    blocks: List[TextBlock],
    column_positions: List[float],
    expected_headers: List[str],
    tolerance: float = 10.0,
) -> List[str]:
    """Parse cell-based headers (Lefort format).

    When headers are at different x-positions, sort left-to-right
    and map to expected headers.

    Args:
        blocks: Header text blocks (at different x-positions)
        column_positions: Detected column x-positions
        expected_headers: Expected final headers from template
        tolerance: X-position tolerance

    Returns:
        List of headers sorted by x-position
    """
    sorted_blocks = sorted(blocks, key=lambda b: b.x)

    headers = []
    for col_x in column_positions:
        found = None
        for block in sorted_blocks:
            if abs(block.x - col_x) < tolerance:
                found = block.text
                break
        headers.append(found if found else "")

    return headers
