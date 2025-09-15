"""
Utility Functions Module

Provides core functionality for PDF processing, OCR, image handling,
and data manipulation used throughout the invoice analyst application.
"""

import hashlib
import io
import difflib
import base64
import fitz
import pathlib
from io import BytesIO
from typing import List, Dict, Any, Tuple, Optional, Union
from PIL import Image
from mistralai import DocumentURLChunk, TextChunk, Mistral
from mistralai.models import OCRResponse
import streamlit.components.v1 as components


def pil_image_to_base64(img: Image.Image) -> str:
    """
    Convert PIL Image to base64 encoded string.

    Args:
        img (PIL.Image): PIL Image object

    Returns:
        str: Base64 encoded image string with data URI prefix
    """
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def remove_redundant_lines_keep_first(
    ocr_pages: List[str], min_repeats: int = 2
) -> str:
    """
    Remove redundant lines that appear on multiple pages, keeping only the first occurrence.

    This is useful for removing repeated headers and footers from multi-page documents.

    Args:
        ocr_pages (list): List of page content strings
        min_repeats (int, optional): Minimum occurrences to consider a line redundant. Defaults to 2.

    Returns:
        str: Cleaned text with redundant lines removed
    """
    from collections import Counter

    # Split each page into lines
    page_lines = [page.splitlines() for page in ocr_pages]
    all_lines = [line.strip() for lines in page_lines for line in lines if line.strip()]
    line_counts = Counter(all_lines)

    # Find lines that are repeated on at least min_repeats pages
    redundant_lines = {
        line for line, count in line_counts.items() if count >= min_repeats
    }

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
        markdown_str = markdown_str.replace(
            f"![{img_name}]({img_name})", f"![{img_name}]({base64_str})"
        )
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
    redundant_lines = {
        line for line, count in line_counts.items() if count >= min_repeats
    }

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


def extract_articles_ocr_from_pdf(pdf_file: Any, client: Mistral) -> str:
    """
    Extract text content from PDF using Mistral OCR API.

    Args:
        pdf_file: Streamlit uploaded file object
        client: Mistral API client instance

    Returns:
        str: Combined markdown content from all pages
    """
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
        model="mistral-ocr-latest",
        include_image_base64=True,
    )

    # Step 4: Collect results
    return get_combined_markdown(response)


def structure_data_chat(
    client: Mistral,
    prompt: str,
    response_format: Dict[str, Any],
    model: str = "pixtral-12b-latest",
) -> str:
    """
    Use Mistral chat API to structure extracted data according to a prompt.

    Args:
        client: Mistral API client instance
        prompt (str): Instruction prompt for data structuring
        response_format (dict): Expected response format specification
        model (str, optional): Model to use. Defaults to "pixtral-12b-latest".

    Returns:
        str: Structured response from the model
    """
    response = client.chat.complete(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    TextChunk(text=prompt),
                ],
            }
        ],
        response_format=response_format,
        temperature=0,
    )
    extracted_data = response.choices[0].message.content
    return extracted_data


def is_float_equal(
    val1: Union[str, float], val2: Union[str, float], tol: float = 1e-2
) -> bool:
    """Check if two strings represent floats that are equal within a tolerance."""
    try:
        f1 = float(str(val1).replace(",", "."))
        f2 = float(str(val2).replace(",", "."))
        return abs(f1 - f2) < tol
    except Exception:
        return False


def fuzzy_in_line(
    value: Union[str, float], line_elements: List[str], threshold: float = 0.85
) -> bool:
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


def find_missing_values_in_line(
    line_text: str, rule_data: Dict[str, Any]
) -> List[Tuple[str, Any]]:
    """
    Returns a list of (key, value) pairs from rule_data that are not found in line_text,
    using fuzzy and numeric matching.
    """
    # Split line into elements
    clean_line = line_text.replace("\xa0", " ")
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


def highlight_pdf_with_rules(
    uploaded_file: Any, rules: List[Dict[str, Any]]
) -> BytesIO:
    """
    Add annotations and highlights to PDF based on extraction rules.

    Lines containing rule['text'] are highlighted. If any values from rule['data']
    are missing from the line, the highlight is red with missing values listed.

    Args:
        uploaded_file: Streamlit uploaded PDF file
        rules (list): List of rule dictionaries with 'text', 'data', and optional 'color'

    Returns:
        io.BytesIO: Annotated PDF as BytesIO object
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
                        content = "\n".join(
                            f"{k}: {v}" for k, v in rule["data"].items()
                        )
                        not_found = find_missing_values_in_line(
                            line_text_in_rect, rule["data"]
                        )
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


def img_to_bytes(img_path: Union[str, pathlib.Path]) -> str:
    img_bytes = pathlib.Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded


def displayPDF__(uploaded_file: Any) -> str:
    bytes_data = uploaded_file.getvalue()
    base64_pdf = base64.b64encode(bytes_data).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    return pdf_display


def displayPDF(pdf_url: str) -> str:
    pdf_display = f"""
        <iframe src="https://mozilla.github.io/pdf.js/web/viewer.html?file={pdf_url}" width="100%" height="800" type="application/pdf"></iframe>
    """
    return pdf_display


def displayPDF__(uploaded_file: Any) -> str:
    bytes_data = uploaded_file.getvalue()
    base64_pdf = base64.b64encode(bytes_data).decode("utf-8")
    pdf_display = f"""
        <embed src="data:application/pdf;base64,{base64_pdf}" 
               width="100%" height="800" type="application/pdf">
    """
    return pdf_display


def generate_invoice_unique_id(
    invoice_numero: Union[str, int], fournisseur_id: Optional[Union[str, int]] = None
) -> str:
    """
    Generate a unique hash ID from invoice number and optional supplier ID.

    Args:
        invoice_numero (str): Invoice number
        fournisseur_id (str, optional): Supplier ID for additional uniqueness

    Returns:
        str: 12-character hash string
    """
    if fournisseur_id is not None:
        base = f"{fournisseur_id}_{invoice_numero}"
    else:
        base = str(invoice_numero)
    return hashlib.sha256(base.encode()).hexdigest()[:12]  # 12 chars is usually enough


def get_unique_id_from_invoice_numero(
    invoice_numero: Union[str, int], fournisseur_id: Optional[Union[str, int]] = None
) -> str:
    """Retrieve the unique id from invoice_numero (and optionally fournisseur_id)."""
    return generate_invoice_unique_id(invoice_numero, fournisseur_id)


def get_id_from_name(mapping: Dict[Any, str], name: str) -> Optional[Any]:
    """Return ID from mapping by value, or None if not found."""
    if not name:
        return None
    return next((k for k, v in mapping.items() if v == name), None)


def store_pdf_supabase(
    supabase, bucket: str, uploaded_file: Any, file_name: str
) -> str:
    """Upload PDF to Supabase storage and return public URL. If file exists, do nothing."""
    # List files in the target folder
    folder = "/".join(file_name.split("/")[:-1])
    files = supabase.storage.from_(bucket).list(folder)
    file_names = [f["name"] for f in files if "name" in f]
    base_name = file_name.split("/")[-1]
    if base_name in file_names:
        # File already exists, just return the signed URL
        url_data = supabase.storage.from_(bucket).create_signed_url(file_name, 60 * 60)
        url = url_data.get("signedURL") or url_data.get("url")
        return url

    # If not exists, upload
    supabase.storage.from_(bucket).upload(
        path=file_name,
        file=uploaded_file.getvalue(),
        file_options={"content_type": "application/pdf"},
        upsert=False,  # Don't overwrite
    )
    url_data = supabase.storage.from_(bucket).create_signed_url(file_name, 60 * 60)
    url = url_data.get("signedURL") or url_data.get("url")
    return url
