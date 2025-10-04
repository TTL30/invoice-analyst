"""PDF annotation for metadata highlighting."""

from pydoc import text
import fitz
import json
from typing import List, Dict, Any, Tuple, Union
from dataclasses import dataclass
import re
from difflib import SequenceMatcher
from invoice_analyst.extraction.pdfextract.models import TextBlock


@dataclass
class HighlightMatch:
    """Represents a matched field to highlight."""

    field_name: str
    bbox: Tuple[float, float, float, float]
    page: int
    color: Tuple[float, float, float]


# Standard color palette for 7 metadata fields
FIELD_COLORS = {
    "supplier_name": (0.2, 0.6, 1.0),  # Blue
    "invoice_date": (1.0, 0.5, 0.0),  # Orange
    "invoice_number": (0.5, 0.0, 0.8),  # Purple
    "total_amount": (1.0, 0.0, 0.0),  # Red
    "taxes_amount": (1.0, 0.8, 0.0),  # Yellow
    "total_without_taxes": (0.8, 0.0, 0.4),  # Magenta
}

# Article validation colors
ARTICLE_VALID_COLOR = (0.0, 1.0, 0.0)  # Green
ARTICLE_INVALID_COLOR = (1.0, 0.0, 0.0)  # Red

# Y-coordinate tolerance for same row detection
ROW_TOLERANCE = 5.0


def fuzzy_match_in_text(search_value: str, text_block: str) -> bool:
    """Fuzzy match allowing small OCR and spacing differences."""
    if not search_value or not text_block:
        return False

    search = re.sub(r"\s+", " ", search_value.strip().lower())
    block = re.sub(r"\s+", " ", text_block.strip().lower())

    # 1. Direct substring
    if search in block:
        return True

    # 2. Dot/comma swap
    alt = search.replace(".", ",")
    if alt in block:
        return True

    # Determine if search is numeric (contains only digits, dots, commas)
    is_numeric = bool(re.fullmatch(r"[\d.,]+", search))

    # 3. Fuzzy ratio only if it’s *not purely numeric*
    if not is_numeric:
        ratio = SequenceMatcher(None, search, block).ratio()
        if ratio > 0.60:
            return True

    # 4. Token-based fuzzy match (for slightly reordered or joined words)
    search_tokens = set(search.split())
    block_tokens = set(block.split())
    overlap = len(search_tokens & block_tokens) / max(len(search_tokens), 1)
    if overlap > 0.8:
        return True

    return False


def extract_metadata_fields(json_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract and normalize metadata fields from JSON.

    Args:
        json_data: Mistral extraction output

    Returns:
        Dictionary mapping field names to normalized values
    """
    fields = {}

    # Extract 7 metadata fields (ignore articles)
    field_mappings = [
        "supplier_name",
        "invoice_date",
        "invoice_number",
        "total_amount",
        "taxes_amount",
        "total_without_taxes",
    ]

    for field in field_mappings:
        value = json_data.get(field)
        if value is not None:
            # Normalize: convert to string, strip whitespace
            fields[field] = str(value).strip()

    return fields


def find_metadata_matches(
    pdf_input: Union[bytes, str], metadata_fields: Dict[str, str]
) -> List[HighlightMatch]:
    """Find all matches for metadata fields in PDF.

    Args:
        pdf_input: PDF as bytes or file path
        metadata_fields: Dictionary of field names to values

    Returns:
        List of HighlightMatch objects for all matches found
    """
    matches = []
    if isinstance(pdf_input, bytes):
        doc = fitz.open(stream=pdf_input, filetype="pdf")
    else:
        doc = fitz.open(pdf_input)

    for field_name, field_value in metadata_fields.items():
        if not field_value:
            continue

        color = FIELD_COLORS.get(field_name, (0, 0, 1))

        # Search on all pages
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Search for exact value
            rects = page.search_for(field_value)

            # If not found, try with comma for numbers
            if not rects and "." in field_value:
                field_value_alt = field_value.replace(".", ",")
                rects = page.search_for(field_value_alt)

            # Add all found rectangles
            for rect in rects:
                matches.append(
                    HighlightMatch(
                        field_name=field_name,
                        bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                        page=page_num,
                        color=color,
                    )
                )

    doc.close()
    return matches


def find_all_article_rows(
    pdf_input: Union[bytes, str], article_number: str
) -> List[Tuple[int, fitz.Rect, str]]:
    """Find all article rows in PDF using article_number as anchor.

    Args:
        pdf_input: PDF as bytes or file path
        article_number: Article reference number to search for

    Returns:
        List of tuples (page_number, row_bbox, row_text) for each occurrence
    """
    if isinstance(pdf_input, bytes):
        doc = fitz.open(stream=pdf_input, filetype="pdf")
    else:
        doc = fitz.open(pdf_input)
    all_rows = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]

        # Search for article number on this page
        rects = page.search_for(article_number)

        # Get all text blocks for this page once
        text_dict = page.get_text("dict")

        # Process each occurrence of the article number
        for anchor_rect in rects:
            anchor_y = (anchor_rect.y0 + anchor_rect.y1) / 2
            anchor_x = anchor_rect.x0

            # Get all text blocks on same row
            row_rects = []
            row_texts = []

            # Define max horizontal distance (typical invoice table width)
            MAX_ROW_WIDTH = 600

            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_bbox = span.get("bbox", [])
                            span_y = (span_bbox[1] + span_bbox[3]) / 2
                            span_x = span_bbox[0]

                            # Check if on same row AND within horizontal range
                            if abs(
                                span_y - anchor_y
                            ) < ROW_TOLERANCE and "Duplicata" not in span.get("text", ""):
                                # Only include spans within reasonable horizontal distance
                                if abs(span_x - anchor_x) < MAX_ROW_WIDTH:
                                    row_rects.append(fitz.Rect(span_bbox))
                                    row_texts.append(span.get("text", ""))

            if row_rects:
                # Calculate bbox covering entire row
                min_x = min(r.x0 for r in row_rects)
                max_x = max(r.x1 for r in row_rects)
                min_y = min(r.y0 for r in row_rects)
                max_y = max(r.y1 for r in row_rects)

                row_bbox = fitz.Rect(min_x, min_y, max_x, max_y)
                row_text = " ".join(row_texts)

                all_rows.append((page_idx, row_bbox, row_text))

    doc.close()
    return all_rows


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace by collapsing multiple spaces into one.

    Args:
        text: Text to normalize

    Returns:
        Text with normalized whitespace
    """
    import re

    return re.sub(r"\s+", " ", text.strip().lower())


def validate_article_fields(
    article: Dict[str, Any], row_text: str
) -> Tuple[bool, Dict[str, Dict[str, str]]]:
    """Validate article fields against row text.

    Args:
        article: Article data from JSON
        row_text: Text content of the article row

    Returns:
        Tuple of (all_valid, discrepancies) where discrepancies maps
        field_name -> {"Extractor": extractor_value, "pdf": pdf_value_or_not_found}
    """
    row_text_normalized = normalize_whitespace(row_text)
    discrepancies = {}

    # 5 required fields
    fields_to_validate = {
        "Désignation": article.get("Désignation", ""),
        "Prix Unitaire": article.get("Prix Unitaire", ""),
        "Packaging": article.get("Packaging", ""),
        "Quantité": article.get("Quantité", ""),
        "Total": article.get("Total", ""),
    }

    for field_name, field_value in fields_to_validate.items():
        if not field_value and field_value != 0:
            discrepancies[field_name] = {
                "Extractor": str(field_value),
                "pdf": "NOT FOUND",
            }
            continue

        value_str = normalize_whitespace(str(field_value))

        if fuzzy_match_in_text(value_str, row_text_normalized):
            continue

        # Field not found - record discrepancy
        discrepancies[field_name] = {"Extractor": str(field_value), "pdf": "NOT FOUND"}

    all_valid = len(discrepancies) == 0
    return (all_valid, discrepancies)


def find_article_matches(
    pdf_input: Union[bytes, str], articles: List[Dict[str, Any]]
) -> List[Tuple[HighlightMatch, Dict[str, Dict[str, str]]]]:
    """Find and validate all articles in PDF.

    Args:
        pdf_input: PDF as bytes or file path
        articles: List of article dictionaries from JSON

    Returns:
        List of tuples (HighlightMatch, discrepancies_dict) for article rows
    """
    matches = []

    # Group articles by reference to handle duplicates
    article_groups = {}
    for article in articles:
        article_number = str(article.get("Reference", ""))
        if not article_number:
            print(f"Warning: Article missing Reference field, skipping")
            continue

        if article_number not in article_groups:
            article_groups[article_number] = []
        article_groups[article_number].append(article)

    # Process each unique article reference
    for article_number, article_list in article_groups.items():
        # Find all rows in PDF with this article number
        all_rows = find_all_article_rows(pdf_input, article_number)

        if not all_rows:
            print(f"Warning: Article {article_number} not found in PDF")
            continue

        # Match each JSON article to a row
        if len(article_list) != len(all_rows):
            print(
                f"Warning: Article {article_number} appears {len(article_list)} times in JSON but {len(all_rows)} times in PDF"
            )

        # Match articles to rows (pair them up)
        for i, article in enumerate(article_list):
            if i >= len(all_rows):
                print(
                    f"Warning: Not enough PDF rows for article {article_number}, skipping extra JSON entries"
                )
                break

            page_num, row_bbox, row_text = all_rows[i]

            # Validate fields
            all_valid, discrepancies = validate_article_fields(article, row_text)

            # Determine color
            color = ARTICLE_VALID_COLOR if all_valid else ARTICLE_INVALID_COLOR

            if not all_valid:
                failed_fields = list(discrepancies.keys())
                print(
                    f"Article {article_number} (occurrence {i+1}) validation failed: {', '.join(failed_fields)}"
                )

            # Create highlight match (store discrepancies for later use)
            match = HighlightMatch(
                field_name=f"article_{article_number}_{i}",
                bbox=(row_bbox.x0, row_bbox.y0, row_bbox.x1, row_bbox.y1),
                page=page_num,
                color=color,
            )
            matches.append((match, discrepancies))

    return matches


def create_sticky_note(
    page: fitz.Page,
    bbox: Tuple[float, float, float, float],
    discrepancies: Dict[str, Dict[str, str]],
    icon: str = "Note",
) -> None:
    """Add sticky note annotation to PDF page.

    Args:
        page: PyMuPDF page object
        bbox: Bounding box (x0, y0, x1, y1) for note position
        discrepancies: Dict mapping field_name -> {Extractor, pdf}
        icon: Icon type (Note, Comment, Help, etc.)
    """
    if not discrepancies:
        return

    # Build note content
    note_lines = []
    for field_name, values in discrepancies.items():
        extractor_val = values["Extractor"]
        pdf_val = values["pdf"]
        note_lines.append(f"{field_name}:")
        note_lines.append(f"  Extractor: {extractor_val}")
        note_lines.append(f"  PDF: {pdf_val}")
        note_lines.append("")

    note_content = "\n".join(note_lines).strip()

    # Position note at top-right corner of bbox
    point = fitz.Point(bbox[2], bbox[1])

    # Create text annotation (sticky note)
    annot = page.add_text_annot(point, note_content, icon=icon)

    # Set annotation properties for better visibility
    annot.set_colors(stroke=(1, 0, 0))  # Red icon
    annot.set_opacity(0.8)
    annot.update()


def extract_text_blocks_from_pdf(pdf_input: Union[bytes, str]) -> List[TextBlock]:
    """Extract all text blocks from all pages of PDF.

    Args:
        pdf_input: PDF as bytes or file path

    Returns:
        List of TextBlock objects from all pages
    """
    if isinstance(pdf_input, bytes):
        doc = fitz.open(stream=pdf_input, filetype="pdf")
    else:
        doc = fitz.open(pdf_input)
    blocks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            blocks.append(
                                TextBlock(
                                    text=text,
                                    x=bbox[0],
                                    y=bbox[1],
                                    page=page_num,
                                    bbox=tuple(bbox),  # Store actual text bbox
                                )
                            )

    doc.close()
    return blocks


def generate_color_mapping(
    pdf_input: Union[bytes, str], json_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate color mapping for all extracted fields and articles.

    Args:
        pdf_input: PDF as bytes or file path
        json_data: Dictionary with Mistral extraction results

    Returns:
        Dictionary containing:
        - metadata_colors: Dict mapping field names to RGB colors (as hex strings)
        - article_colors: List of RGB colors (as hex strings) for each article
    """

    def rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
        """Convert RGB tuple (0-1 range) to hex color string."""
        r = int(rgb[0] * 255)
        g = int(rgb[1] * 255)
        b = int(rgb[2] * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    # Extract metadata fields
    metadata_fields = extract_metadata_fields(json_data)

    # Build metadata color mapping
    metadata_colors = {}
    for field_name in metadata_fields.keys():
        color = FIELD_COLORS.get(field_name, (0, 0, 1))
        metadata_colors[field_name] = rgb_to_hex(color)

    # Find article matches to determine colors
    articles = json_data.get("articles", [])
    article_matches_with_discrepancies = find_article_matches(pdf_input, articles)

    # Build article color list (one color per article in order)
    article_colors = []
    for match, discrepancies in article_matches_with_discrepancies:
        article_colors.append(rgb_to_hex(match.color))

    # Fill remaining articles with default valid color if they weren't found in PDF
    while len(article_colors) < len(articles):
        article_colors.append(rgb_to_hex(ARTICLE_VALID_COLOR))

    return {"metadata_colors": metadata_colors, "article_colors": article_colors}


def annotate_pdf(pdf_input: Union[bytes, str], json_data: Dict[str, Any]) -> bytes:
    """Generate annotated PDF with metadata and article highlights.

    Args:
        pdf_input: PDF as bytes or file path
        json_data: Dictionary with Mistral extraction results

    Returns:
        Annotated PDF as bytes

    Raises:
        Exception: If annotation fails
    """
    # Extract metadata fields
    metadata_fields = extract_metadata_fields(json_data)

    # Find metadata matches
    metadata_matches = find_metadata_matches(pdf_input, metadata_fields)

    # Find article matches
    articles = json_data.get("articles", [])
    article_matches_with_discrepancies = find_article_matches(pdf_input, articles)

    # Open PDF for annotation
    try:
        if isinstance(pdf_input, bytes):
            doc = fitz.open(stream=pdf_input, filetype="pdf")
        else:
            doc = fitz.open(pdf_input)
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found: {pdf_input}")
    except Exception as e:
        raise Exception(f"Failed to open PDF: {e}")

    # Draw metadata highlights
    for match in metadata_matches:
        page = doc[match.page]
        rect = fitz.Rect(match.bbox)

        page.draw_rect(rect, color=match.color, fill=match.color, fill_opacity=0.3, width=0)

    # Draw article highlights and add sticky notes for invalid articles
    for match, discrepancies in article_matches_with_discrepancies:
        page = doc[match.page]
        rect = fitz.Rect(match.bbox)

        # Draw highlight
        page.draw_rect(rect, color=match.color, fill=match.color, fill_opacity=0.3, width=0)

        # Add sticky note if article has discrepancies
        if discrepancies:
            create_sticky_note(page, match.bbox, discrepancies)

    # Return annotated PDF as bytes
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
