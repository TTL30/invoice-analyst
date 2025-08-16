import os
import io
import json
import difflib
import base64
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

def convert_pdf_to_image_data(pdf_bytes, lang='eng'):
   images = convert_from_bytes(pdf_bytes)
   images_data = []
   for img in images:
       img_data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
       images_data.append(img_data)
   return images_data

def get_pdf_page_sizes(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    sizes = []
    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        sizes.append((w, h))
    return sizes

def convert_image_coords_to_pdf(x, y, w, h, img_w, img_h, pdf_w, pdf_h):
    x1_pdf = x * (pdf_w / img_w)
    x2_pdf = (x + w) * (pdf_w / img_w)
    y1_pdf = pdf_h - ((y + h) * (pdf_h / img_h))
    y2_pdf = pdf_h - (y * (pdf_h / img_h))
    return x1_pdf, y1_pdf, x2_pdf, y2_pdf

def extract_text_positions_from_images_data(images_data, data_to_research, pdf_bytes, match_threshold=0.8):
    import difflib
    from PIL import Image
    label, text = data_to_research
    annotations = []
    search_words = [w.strip().lower() for w in text.split() if w.strip()]
    n = len(search_words)
    pdf_page_sizes = get_pdf_page_sizes(pdf_bytes)
    images = convert_from_bytes(pdf_bytes)
    for page_num, data in enumerate(images_data):
        img_w, img_h = images[page_num].width, images[page_num].height
        pdf_w, pdf_h = pdf_page_sizes[page_num]
        ocr_words = [w.strip().lower() for w in data['text']]
        i = 0
        while i <= len(ocr_words) - n:
            window = ocr_words[i:i+n]
            window_text = " ".join(window)
            ratio = difflib.SequenceMatcher(None, window_text, text.strip().lower()).ratio()
            if ratio >= match_threshold:
                x = min(data['left'][i:i+n])
                y = min(data['top'][i:i+n])
                w = max([data['left'][j] + data['width'][j] for j in range(i, i+n)]) - x
                h = max([data['top'][j] + data['height'][j] for j in range(i, i+n)]) - y
                x1_pdf, y1_pdf, x2_pdf, y2_pdf = convert_image_coords_to_pdf(
                    x, y, w, h, img_w, img_h, pdf_w, pdf_h
                )
                box = (page_num, x1_pdf, y1_pdf, x2_pdf, y2_pdf, label, (1, 0, 0))
                if box not in annotations:
                    annotations.append(box)
                i += n
            else:
                i += 1
    return annotations