"""PDF annotation helpers based on PyMuPDF."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, Iterable, List, Tuple

import fitz  # type: ignore


@dataclass(slots=True)
class AnnotationRule:
    text: str
    data: Dict[str, object]
    color: tuple[float, float, float] = (0.0, 0.5, 0.0)


def _is_float_equal(val1: object, val2: object, tol: float = 1e-2) -> bool:
    try:
        f1 = float(str(val1).replace(",", "."))
        f2 = float(str(val2).replace(",", "."))
        return abs(f1 - f2) < tol
    except Exception:
        return False


def _fuzzy_in_line(value: object, line_elements: List[str], threshold: float = 0.85) -> bool:
    value_str = str(value).strip()
    for elem in line_elements:
        ratio = difflib.SequenceMatcher(None, value_str, elem).ratio()
        if ratio >= threshold or _is_float_equal(value_str, elem):
            return True
    return False


def _find_missing_values(line_text: str, rule_data: Dict[str, object]) -> List[Tuple[str, object]]:
    clean_line = line_text.replace("\xa0", " ")
    line_elements = clean_line.split()
    working_line = line_elements.copy()
    not_found: List[Tuple[str, object]] = []

    for key, value in rule_data.items():
        found = False
        for idx, elem in enumerate(working_line):
            if _fuzzy_in_line(value, [elem]):
                found = True
                del working_line[idx]
                break
        if not found:
            not_found.append((key, value))
    return not_found


def highlight_pdf(*, pdf_bytes: bytes, rules: Iterable[AnnotationRule]) -> bytes:
    """Apply highlight annotations to the PDF and return the resulting bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        rules_list = list(rules)
        if not rules_list:
            return pdf_bytes

        # Track which rules have been used to handle duplicates correctly
        # Key: (page_num, y0, y1) to identify unique line positions
        used_rule_positions: Dict[int, List[Tuple[float, float]]] = {}

        for page_num, page in enumerate(doc):
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    spans_sorted = sorted(line.get("spans", []), key=lambda s: s["bbox"][0])
                    if not spans_sorted:
                        continue
                    line_text = " ".join(span.get("text", "") for span in spans_sorted).strip()
                    if not line_text:
                        continue

                    y0 = min(span["bbox"][1] for span in spans_sorted)
                    y1 = max(span["bbox"][3] for span in spans_sorted)
                    line_rect = fitz.Rect(0, y0, page.rect.width, y1)
                    text_in_rect = page.get_textbox(line_rect)

                    # Try to match with rules, allowing the same rule to match multiple lines
                    for rule_idx, rule in enumerate(rules_list):
                        if rule.text and rule.text in line_text:
                            # Check if this exact position was already used by this rule
                            if page_num not in used_rule_positions:
                                used_rule_positions[page_num] = []

                            position = (y0, y1, rule_idx)
                            if position in [(p[0], p[1], p[2]) for p in used_rule_positions[page_num]]:
                                # This exact position already annotated by this rule, skip
                                continue

                            used_rule_positions[page_num].append(position)

                            content_lines = [f"{k}: {v}" for k, v in rule.data.items()]
                            missing = _find_missing_values(text_in_rect, rule.data)
                            color = rule.color
                            if missing:
                                color = (1.0, 0.0, 0.0)
                                content_lines.append(
                                    "Something is wrong with this row, check the values:"
                                )
                                for key, value in missing:
                                    content_lines.append(f"- Might be {key}: {value}")

                            annot = page.add_highlight_annot(line_rect)
                            annot.set_colors(stroke=color)
                            annot.set_info(content="\n".join(content_lines))
                            annot.set_opacity(0.2)
                            annot.update()
                            break  # Only one rule per line, but the same rule can match multiple lines
        output_pdf = BytesIO()
        doc.save(output_pdf)
        return output_pdf.getvalue()
    finally:
        doc.close()
