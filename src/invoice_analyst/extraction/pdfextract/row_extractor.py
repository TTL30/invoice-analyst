"""Row extraction with pattern-based detection."""

from typing import List, Dict
from invoice_analyst.extraction.pdfextract.models import TextBlock, TableRow, TableRegion
from invoice_analyst.extraction.pdfextract.utils import normalize_cell_text


def check_alignment(
    row_blocks: List[TextBlock],
    column_positions: List[float],
    tolerance: float = 10.0,
    threshold: float = 0.3,
    min_aligned: int = 2,
) -> bool:
    """Check if row blocks align with column positions.

    Args:
        row_blocks: Text blocks in this row
        column_positions: Expected column x-positions
        tolerance: X-position tolerance in pixels
        threshold: Minimum alignment ratio
        min_aligned: Minimum number of aligned blocks

    Returns:
        True if row aligns with columns
    """
    if not row_blocks:
        return False

    aligned_count = 0
    for block in row_blocks:
        for col_x in column_positions:
            if abs(block.x - col_x) < tolerance:
                aligned_count += 1
                break

    if aligned_count < min_aligned:
        return False

    alignment_ratio = aligned_count / len(row_blocks)
    return alignment_ratio >= threshold


def get_blocks_at_y(blocks: List[TextBlock], y: float, tolerance: float = 5.0) -> List[TextBlock]:
    """Get all blocks at specific y-position.

    Args:
        blocks: All text blocks
        y: Y-position to search
        tolerance: Y-position tolerance

    Returns:
        Blocks at y-position
    """
    return [b for b in blocks if abs(b.y - y) < tolerance]


def cluster_blocks_by_y(
    blocks: List[TextBlock], tolerance: float = 3.0
) -> Dict[float, List[TextBlock]]:
    """Cluster blocks by y-position into logical rows.

    Args:
        blocks: All text blocks
        tolerance: Y-position clustering tolerance

    Returns:
        Dictionary mapping representative y to blocks in that row
    """
    if not blocks:
        return {}

    sorted_blocks = sorted(blocks, key=lambda b: b.y)
    clusters = {}
    current_y = None
    current_cluster = []

    for block in sorted_blocks:
        if current_y is None or abs(block.y - current_y) < tolerance:
            if current_y is None:
                current_y = block.y
            current_cluster.append(block)
        else:
            clusters[current_y] = current_cluster
            current_y = block.y
            current_cluster = [block]

    if current_cluster:
        clusters[current_y] = current_cluster

    return clusters


def is_detail_row(blocks: List[TextBlock], patterns: List[str] = None) -> bool:
    """Check if row is a detail row based on patterns.

    Args:
        blocks: Text blocks in row
        patterns: List of patterns to check (from template)

    Returns:
        True if detail row
    """
    if not blocks or not patterns:
        return False

    first_text = blocks[0].text.strip()
    return any(first_text.startswith(pattern) for pattern in patterns)


def is_summary_row(blocks: List[TextBlock], patterns: List[str] = None) -> bool:
    """Check if row is a summary/separator row based on patterns.

    Args:
        blocks: Text blocks in row
        patterns: List of patterns to check (from template)

    Returns:
        True if summary row
    """
    if not blocks or not patterns:
        return False

    first_text = blocks[0].text.strip()
    return any(first_text.startswith(pattern) for pattern in patterns)


def is_footer_row(blocks: List[TextBlock], keywords: List[str] = None) -> bool:
    """Check if row is a footer/summary table row based on keywords.

    Args:
        blocks: Text blocks in row
        keywords: List of keywords to check (from template)

    Returns:
        True if footer row
    """
    if not blocks or not keywords:
        return False

    text = " ".join(b.text for b in blocks).strip()
    return any(keyword in text for keyword in keywords)


def extract_rows(
    blocks: List[TextBlock],
    table_region: TableRegion,
    row_height: float,
    template,
    max_misaligned: int = 10,
    tolerance: float = 10.0,
) -> List[TableRow]:
    """Extract table rows using y-cluster detection.

    Args:
        blocks: All text blocks for this page
        table_region: Table region info
        row_height: Average row height (not used in cluster mode)
        max_misaligned: Maximum consecutive misaligned lines before stopping
        tolerance: X-position tolerance

    Returns:
        List of extracted table rows
    """
    table_blocks = [b for b in blocks if b.y >= table_region.start_y]

    if not table_blocks:
        return []

    clusters = cluster_blocks_by_y(table_blocks, tolerance=3.0)

    rows = []
    consecutive_misaligned = 0

    config = template.table

    for y in sorted(clusters.keys()):
        row_blocks = clusters[y]

        if is_summary_row(row_blocks, config.summary_patterns):
            consecutive_misaligned = 0
            continue

        if is_detail_row(row_blocks, config.detail_patterns):
            consecutive_misaligned = 0
            continue

        if is_footer_row(row_blocks, config.footer_keywords):
            break

        if check_alignment(
            row_blocks,
            table_region.column_positions,
            tolerance,
            config.alignment_threshold,
            config.min_aligned_blocks,
        ):
            cells = build_row_cells(
                row_blocks,
                table_region.column_positions,
                tolerance,
                config.skip_chars,
                config.use_data_driven_boundaries,
                config.column_char_offsets,
                config.column_offset_variants,
            )

            if any(cell.strip() for cell in cells):
                rows.append(TableRow(cells=cells, y=y, page=table_region.page))
                consecutive_misaligned = 0
        else:
            consecutive_misaligned += 1
            if consecutive_misaligned >= max_misaligned:
                break

    return rows if len(rows) >= 1 else []


def select_column_offsets(
    text: str,
    char_offsets: List[int],
    variants: List = None,
) -> tuple[List[int], bool]:
    """Select appropriate column offsets based on text pattern.

    Args:
        text: Full row text string
        char_offsets: Default character offsets from template
        variants: Optional list of ColumnVariant objects from template

    Returns:
        Tuple of (selected_offsets, prepend_empty_cell)
    """
    import re

    if not variants:
        return char_offsets, False

    # Try each variant's detection pattern
    for variant in variants:
        # Extract first field based on default offsets to test pattern
        first_field_end = char_offsets[1] if len(char_offsets) > 1 else 20
        first_field = text[:first_field_end].strip()
        first_word = first_field.split()[0] if first_field else ""

        # Check if first word matches this variant's pattern
        if re.match(variant.detect_pattern, first_word):
            # Check if this variant has same offsets as default (means column is present)
            if variant.offsets == char_offsets:
                return variant.offsets, False
            else:
                # Different offsets means column is missing - prepend empty cell
                return variant.offsets, True

    # No variant matched, use default
    return char_offsets, False


def parse_text_based_row(
    text: str,
    column_positions: List[float],
    base_x: float,
    char_offsets: List[int] = None,
    column_variants: List = None,
) -> List[str]:
    """Parse single-block row by fixed-width positions with smart numeric extraction.

    For text-based PDFs where row data is in one continuous string,
    extract cells using character offsets but extract numeric values
    from the designation field if they appear there.

    Args:
        text: Full row text string
        column_positions: Column x-positions (pixel/point positions, used for cell count)
        base_x: Base x-position (first column start)
        char_offsets: Optional explicit character offsets from template
        column_variants: Optional list of ColumnVariant objects for dynamic offset selection

    Returns:
        List of cell values padded/truncated to match column count
    """
    import re

    if not char_offsets:
        offsets = [int(pos - base_x) for pos in column_positions]
    else:
        offsets = char_offsets

    # Select appropriate offsets based on column variants (if any)
    prepend_empty = False
    if char_offsets and column_variants:
        offsets, prepend_empty = select_column_offsets(text, char_offsets, column_variants)

    cells = []

    for i in range(len(offsets)):
        start = offsets[i]
        end = offsets[i + 1] if i + 1 < len(offsets) else len(text)
        cell_text = text[start:end].strip() if start < len(text) else ""
        cells.append(normalize_cell_text(cell_text))

    # Prepend empty cell if variant indicated missing first column
    if prepend_empty:
        cells.insert(0, "")

    if char_offsets and len(cells) > 2:
        designation = cells[2]
        numeric_matches = re.findall(r"(?:^|\s)(\d+[,\.]\d+)(?:\s|$)", designation)

        if numeric_matches:
            cleaned_designation = designation
            for num in numeric_matches:
                cleaned_designation = cleaned_designation.replace(num, "").strip()

            cells[2] = cleaned_designation

            empty_field_idx = 3
            for num in numeric_matches:
                while empty_field_idx < len(cells) and cells[empty_field_idx]:
                    empty_field_idx += 1
                if empty_field_idx < len(cells):
                    cells[empty_field_idx] = num
                    empty_field_idx += 1

    while len(cells) < len(column_positions):
        cells.append("")

    return cells


def build_row_cells(
    row_blocks: List[TextBlock],
    column_positions: List[float],
    tolerance: float = 15.0,
    skip_chars: List[str] = None,
    use_data_driven: bool = False,
    char_offsets: List[int] = None,
    column_variants: List = None,
) -> List[str]:
    """Build cells using range-based assignment with adjusted boundaries.

    Args:
        row_blocks: Text blocks in this row
        column_positions: Column x-positions
        tolerance: Tolerance for first column exact matching
        skip_chars: Characters to filter out (from template)
        use_data_driven: Use data-driven boundaries for narrow columns
        char_offsets: Optional explicit character offsets from template
        column_variants: Optional list of ColumnVariant objects for dynamic offset selection

    Returns:
        List of cell values (empty string for missing cells)
    """
    if not row_blocks or not column_positions:
        return [""] * len(column_positions)

    skip_set = set(skip_chars) if skip_chars else set()
    filtered_blocks = [b for b in row_blocks if b.text.strip() not in skip_set]

    first_col_blocks = [b for b in filtered_blocks if abs(b.x - column_positions[0]) < tolerance]

    if len(first_col_blocks) >= 1 and len(first_col_blocks) == len(filtered_blocks):
        longest_block = max(first_col_blocks, key=lambda b: len(b.text))
        return parse_text_based_row(
            longest_block.text, column_positions, column_positions[0], char_offsets, column_variants
        )

    cells = [[] for _ in column_positions]

    sorted_blocks = sorted(filtered_blocks, key=lambda b: b.x)

    boundaries = []
    for i in range(len(column_positions) - 1):
        curr_col = column_positions[i]
        next_col = column_positions[i + 1]
        col_gap = next_col - curr_col

        if use_data_driven and col_gap < 60:
            blocks_between = [b for b in sorted_blocks if curr_col < b.x < next_col]

            if blocks_between:
                x_positions = [b.x for b in blocks_between]
                if len(x_positions) == 1:
                    boundary = (x_positions[0] + next_col) / 2
                else:
                    x_positions_sorted = sorted(x_positions)
                    boundary = (x_positions_sorted[0] + x_positions_sorted[-1]) / 2
            else:
                boundary = (curr_col + next_col) / 2
        else:
            boundary = (curr_col + next_col) / 2

        boundaries.append(boundary)
    boundaries.append(float("inf"))

    for block in filtered_blocks:
        if abs(block.x - column_positions[0]) < tolerance:
            cells[0].append(block)
        else:
            assigned = False
            for i in range(1, len(column_positions)):
                prev_col = column_positions[i - 1]
                curr_col = column_positions[i]
                next_boundary = boundaries[i]

                if i == 1:
                    prev_boundary = prev_col
                    if block.x > prev_boundary and block.x < next_boundary:
                        cells[i].append(block)
                        assigned = True
                        break
                else:
                    prev_boundary = boundaries[i - 1]
                    if prev_boundary <= block.x < next_boundary:
                        cells[i].append(block)
                        assigned = True
                        break

            if not assigned and block.x >= column_positions[-1]:
                cells[-1].append(block)

    result = []
    for cell_blocks in cells:
        if cell_blocks:
            sorted_blocks = sorted(cell_blocks, key=lambda b: b.x)
            cell_text = " ".join(b.text for b in sorted_blocks)
            result.append(normalize_cell_text(cell_text))
        else:
            result.append("")

    return result
