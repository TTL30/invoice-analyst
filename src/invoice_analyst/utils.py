import os
import io
import json
import difflib
import base64
import fitz
import pytesseract
from PyPDF2 import PdfReader
import pandas as pd
from io import BytesIO
from PIL import Image
from mistralai import DocumentURLChunk, TextChunk
from mistralai.models import OCRResponse
from pdf2image import convert_from_bytes

def pil_image_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"

def remove_redundant_lines_keep_first(ocr_pages, min_repeats=2):
    """
    Removes redundant lines that appear on multiple pages, but keeps their first occurrence (usually from the first page).
    """
    from collections import Counter

    # Split each page into lines
    page_lines = [page.splitlines() for page in ocr_pages]
    all_lines = [line.strip() for lines in page_lines for line in lines if line.strip()]
    line_counts = Counter(all_lines)

    # Find lines that are repeated on at least min_repeats pages
    redundant_lines = {line for line, count in line_counts.items() if count >= min_repeats}

    # Track which redundant lines have already been kept
    kept_redundant = set()
    cleaned_pages = []
    for lines in page_lines:
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped in redundant_lines:
                if stripped not in kept_redundant:
                    cleaned.append(line)
                    kept_redundant.add(stripped)
                # else: skip this redundant line (already kept once)
            else:
                cleaned.append(line)
        cleaned_pages.append("\n".join(cleaned))

    return "\n".join(cleaned_pages)

def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    for img_name, base64_str in images_dict.items():
        markdown_str = markdown_str.replace(f"![{img_name}]({img_name})", f"![{img_name}]({base64_str})")
    return markdown_str

def get_combined_markdown(ocr_response: OCRResponse) -> str:
  markdowns: list[str] = []
  for page in ocr_response.pages:
    image_data = {}
    for img in page.images:
      image_data[img.id] = img.image_base64
    markdowns.append(replace_images_in_markdown(page.markdown, image_data))

  return "\n\n".join(markdowns)

def postprocess_markdown_remove_redundant(markdown: str, min_repeats: int = 2) -> str:
    """
    Removes redundant lines that appear on multiple pages in the markdown,
    but keeps their first occurrence (useful for repeated headers/footers).
    """
    # Split markdown into pages if you use a delimiter, else just lines
    lines = markdown.splitlines()
    from collections import Counter

    # Count all non-empty lines
    all_lines = [line.strip() for line in lines if line.strip()]
    line_counts = Counter(all_lines)

    # Find lines that are repeated at least min_repeats times
    redundant_lines = {line for line, count in line_counts.items() if count >= min_repeats}

    kept_redundant = set()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped in redundant_lines:
            if stripped not in kept_redundant:
                cleaned.append(line)
                kept_redundant.add(stripped)
            # else: skip this redundant line (already kept once)
        else:
            cleaned.append(line)
    return "\n".join(cleaned)

def extract_articles_ocr_from_pdf(pdf_file, client):
    uploaded_file = client.files.upload(
        file={
            "file_name": pdf_file.name,
            "content": pdf_file.read(),
        },
        purpose="ocr",
    )

    signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=60)

    response = client.ocr.process(
        document=DocumentURLChunk(document_url=signed_url.url), 
        model="mistral-ocr-latest", include_image_base64=True
    )

    # Step 4: Collect results
    return get_combined_markdown(response)

def structure_data_chat(client, prompt, response_format, model="pixtral-12b-latest"):
    response = client.chat.complete(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [TextChunk(
                    text=prompt
                    ),]
            }
        ],
        response_format=response_format,
        temperature=0,
    )
    extracted_data = response.choices[0].message.content
    return extracted_data


def is_float_equal(val1, val2, tol=1e-2):
    """Check if two strings represent floats that are equal within a tolerance."""
    try:
        f1 = float(str(val1).replace(",", "."))
        f2 = float(str(val2).replace(",", "."))
        return abs(f1 - f2) < tol
    except Exception:
        return False

def fuzzy_in_line(value, line_elements, threshold=0.85):
    """Return True if value is fuzzily present in line_elements or numerically equal."""
    value_str = str(value).strip()
    for elem in line_elements:
        # Fuzzy string match
        ratio = difflib.SequenceMatcher(None, value_str, elem).ratio()
        if ratio >= threshold:
            return True
        # Numeric match
        if is_float_equal(value_str, elem):
            return True
    return False

def find_missing_values_in_line(line_text, rule_data):
    """
    Returns a list of (key, value) pairs from rule_data that are not found in line_text,
    using fuzzy and numeric matching.
    """
    # Split line into elements
    clean_line = line_text.replace('\xa0', ' ')
    line_elements = clean_line.split()
    # Copy for destructive matching
    working_line = line_elements.copy()
    not_found = []

    for k, v in rule_data.items():
        found = False
        for idx, elem in enumerate(working_line):
            if fuzzy_in_line(v, [elem]):
                found = True
                del working_line[idx]  # Remove only the first match
                break
        if not found:
            not_found.append((k, v))
    return not_found

def highlight_pdf_with_rules(uploaded_file, rules):
    """
    Highlights lines in a PDF where rule['text'] is found (line mode only).
    If any value in rule['data'] is not found in the line, the highlight is red and missing values are listed.
    """
    doc = fitz.open(stream=uploaded_file.getvalue(), filetype="pdf")

    for page in doc:
        text_dict = page.get_text("dict")
        for block in text_dict["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                # Sort spans left-to-right and join their text
                spans_sorted = sorted(line["spans"], key=lambda s: s["bbox"][0])
                line_text = " ".join(span["text"] for span in spans_sorted).strip()

                for rule in rules:
                    if rule["text"] in line_text:
                        color = rule.get("color", (0, 0.5, 0))  # Default green
                        y0 = min(span["bbox"][1] for span in line["spans"])
                        y1 = max(span["bbox"][3] for span in line["spans"])
                        line_rect = fitz.Rect(0, y0, page.rect.width, y1)
                        # Get text in the rectangle (for OCR-imperfect PDFs)
                        line_text_in_rect = page.get_textbox(line_rect)
                        content = "\n".join(f"{k}: {v}" for k, v in rule['data'].items())
                        not_found = find_missing_values_in_line(line_text_in_rect, rule['data'])
                        if not_found:
                            content += f"\n\nSomething is wrong with this row, check the values:"
                            color = (1, 0, 0)  # Red
                            for item in not_found:
                                content += f"\n- Might be {item[0]}: {item[1]}"

                        annot = page.add_highlight_annot(line_rect)
                        annot.set_colors(stroke=color)
                        annot.set_info(content=content)
                        annot.set_opacity(0.2)
                        annot.update()
                        break  # Only annotate the first matching rule per line

    output_pdf = io.BytesIO()
    doc.save(output_pdf)
    doc.close()
    output_pdf.seek(0)  # reset cursor
    return output_pdf