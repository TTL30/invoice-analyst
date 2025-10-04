"""Data models for PDF extraction."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TextBlock:
    """Represents a text block extracted from PDF with position."""

    text: str
    x: float
    y: float
    page: int
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1)


@dataclass
class ColumnVariant:
    """Column offset variant for handling optional columns."""

    offsets: List[int]
    detect_pattern: str  # Regex pattern to match first field when this variant applies


@dataclass
class TableConfig:
    """Table configuration from template."""

    start_anchor: str
    header_rows: int
    header: List[str]
    end_anchor: Optional[str] = None
    footer_keywords: Optional[List[str]] = None
    summary_patterns: Optional[List[str]] = None
    detail_patterns: Optional[List[str]] = None
    skip_chars: Optional[List[str]] = None
    use_data_driven_boundaries: bool = False
    min_aligned_blocks: int = 2
    alignment_threshold: float = 0.3
    column_char_offsets: Optional[List[int]] = None
    column_offset_variants: Optional[List[ColumnVariant]] = None
    excluded_columns: Optional[List[str]] = None


@dataclass
class Template:
    """Supplier template for PDF extraction."""

    supplier: str
    identifiers: List[str]
    table: TableConfig


@dataclass
class TableRow:
    """Represents a single table row with cells."""

    cells: List[str]
    y: float
    page: int


@dataclass
class TableRegion:
    """Represents a detected table region."""

    headers: List[str]
    rows: List[TableRow]
    column_positions: List[float] = field(default_factory=list)
    start_y: float = 0.0
    end_y: float = 0.0
    page: int = 0
