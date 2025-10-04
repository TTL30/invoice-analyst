"""Utility functions for text matching and processing."""

import re
from typing import List
from invoice_analyst.extraction.pdfextract.models import TextBlock


def fuzzy_match_headers(actual: List[str], expected: List[str], threshold: float = 0.7) -> bool:
    """Fuzzy match headers ignoring special characters and accents.

    Args:
        actual: Actual headers extracted from PDF
        expected: Expected headers from template
        threshold: Minimum match ratio (0-1)

    Returns:
        True if headers match above threshold
    """
    if len(actual) != len(expected):
        return False

    matches = 0
    for act, exp in zip(actual, expected):
        act_clean = re.sub(r"[^\w\s]", "", act.lower())
        exp_clean = re.sub(r"[^\w\s]", "", exp.lower())

        act_norm = act_clean.replace(" ", "").replace("é", "e").replace("è", "e")
        exp_norm = exp_clean.replace(" ", "").replace("é", "e").replace("è", "e")

        if act_norm == exp_norm or act_norm in exp_norm or exp_norm in act_norm:
            matches += 1

    match_ratio = matches / len(expected) if expected else 0
    return match_ratio >= threshold


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and special chars.

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text


def filter_non_table_blocks(all_blocks: List[TextBlock], tables: List) -> List[TextBlock]:
    """Filter out text blocks that are part of detected tables.

    Args:
        all_blocks: All text blocks from PDF
        tables: List of TableRegion objects

    Returns:
        Text blocks that are NOT part of any table
    """
    info_blocks = []

    for block in all_blocks:
        is_in_table = False

        for table in tables:
            # Check if block is within table boundaries
            if block.page == table.page and block.y >= table.start_y:
                # Find end_y of table (last row's y position or use large value)
                if table.rows:
                    table_end_y = max(row.y for row in table.rows) + 20  # Add buffer
                else:
                    table_end_y = table.start_y + 100  # Default buffer

                if block.y <= table_end_y:
                    is_in_table = True
                    break

        if not is_in_table:
            info_blocks.append(block)

    return info_blocks


def deduplicate_blocks(blocks: List[TextBlock]) -> List[TextBlock]:
    """Remove duplicate text blocks using exact text match.

    Preserves first occurrence and maintains reading order.

    Args:
        blocks: List of text blocks

    Returns:
        Deduplicated list of text blocks
    """
    seen_texts = set()
    deduplicated = []

    for block in blocks:
        if block.text not in seen_texts:
            seen_texts.add(block.text)
            deduplicated.append(block)

    return deduplicated


def normalize_cell_text(text: str) -> str:
    """Normalize table cell text by cleaning whitespace.

    Removes excess whitespace while preserving single spaces between words.
    Handles tabs, newlines, and multiple consecutive spaces.

    Args:
        text: Raw cell text

    Returns:
        Normalized cell text with clean single spaces
    """
    # Strip leading/trailing whitespace
    text = text.strip()
    # Replace all whitespace sequences (spaces, tabs, newlines) with single space
    text = re.sub(r"\s+", " ", text)
    return text
