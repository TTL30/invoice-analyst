"""PDF text extraction with position data."""

import fitz
from typing import List, Union
from invoice_analyst.extraction.pdfextract.models import TextBlock


def extract_text_blocks(pdf_input: Union[bytes, str]) -> List[TextBlock]:
    """Extract all text blocks with x/y/page coordinates from PDF.

    Args:
        pdf_input: PDF as bytes or file path string

    Returns:
        List of TextBlock objects with position data

    Raises:
        FileNotFoundError: If PDF file not found (when path provided)
        Exception: If PDF cannot be processed
    """
    try:
        if isinstance(pdf_input, bytes):
            doc = fitz.open(stream=pdf_input, filetype="pdf")
        else:
            doc = fitz.open(pdf_input)
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF file not found: {pdf_input}")
    except Exception as e:
        raise Exception(f"Failed to open PDF: {e}")

    blocks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue

                    bbox = span.get("bbox", [0, 0, 0, 0])
                    x = bbox[0]
                    y = bbox[1]

                    blocks.append(TextBlock(text=text, x=x, y=y, page=page_num))

    doc.close()
    return blocks


def auto_detect_row_height(blocks: List[TextBlock], min_samples: int = 5) -> float:
    """Auto-detect row height using modal spacing.

    Args:
        blocks: List of text blocks
        min_samples: Minimum number of samples to use

    Returns:
        Modal row height in points
    """
    if len(blocks) < min_samples:
        return 15.0

    y_positions = sorted(set(b.y for b in blocks[:100]))

    if len(y_positions) < 2:
        return 15.0

    gaps = []
    for i in range(len(y_positions) - 1):
        gap = y_positions[i + 1] - y_positions[i]
        if 5.0 <= gap <= 30.0:
            gaps.append(gap)

    if not gaps:
        return 15.0

    from collections import Counter

    gap_counts = Counter(round(g, 1) for g in gaps)
    modal_gap = gap_counts.most_common(1)[0][0]

    return float(modal_gap)
