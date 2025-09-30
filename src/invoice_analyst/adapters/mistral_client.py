"""Wrapper utilities around the Mistral AI SDK."""

from __future__ import annotations

from typing import Any, Dict

from mistralai import DocumentURLChunk, Mistral, TextChunk
from mistralai.models import OCRResponse


def _replace_images_in_markdown(markdown_str: str, images_dict: Dict[str, str]) -> str:
    for img_name, base64_str in images_dict.items():
        markdown_str = markdown_str.replace(
            f"![{img_name}]({img_name})", f"![{img_name}]({base64_str})"
        )
    return markdown_str


def _combine_markdown(ocr_response: OCRResponse) -> str:
    markdowns: list[str] = []
    for page in ocr_response.pages:
        image_data = {img.id: img.image_base64 for img in page.images}
        markdowns.append(_replace_images_in_markdown(page.markdown, image_data))

    return "\n\n".join(markdowns)


class MistralAdapter:
    """Small convenience wrapper around the official Python SDK."""

    def __init__(self, api_key: str, ocr_model: str = "mistral-ocr-latest") -> None:
        self._client = Mistral(api_key=api_key)
        self._ocr_model = ocr_model

    @property
    def client(self) -> Mistral:
        return self._client

    def extract_markdown(self, *, file_name: str, content: bytes) -> str:
        """Run OCR extraction and return combined markdown with inline images."""
        uploaded_file = self._client.files.upload(
            file={
                "file_name": file_name,
                "content": content,
            },
            purpose="ocr",
        )
        signed_url = self._client.files.get_signed_url(
            file_id=uploaded_file.id, expiry=60
        )
        response = self._client.ocr.process(
            document=DocumentURLChunk(document_url=signed_url.url),
            model=self._ocr_model,
            include_image_base64=True,
        )
        return _combine_markdown(response)

    def structure(self, *, prompt: str, model: str = "pixtral-12b-latest") -> str:
        """Ask the LLM to structure the invoice data."""
        response = self._client.chat.complete(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [TextChunk(text=prompt)],
                }
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return response.choices[0].message.content


def build_structure_prompt(*, aggregated_ocr: str, example_row: Dict[str, Any], categories: list[str]) -> str:
    """Create the few-shot prompt used to coerce the LLM into structured output."""
    return (
        f"This is the OCR result in markdown format:\n\n{aggregated_ocr}\n\n"
        "Your tasks are:\n"
        "1. Extract and clean only the following invoice information:\n"
        "- Invoice number (Numéro de facture)\n"
        "- Invoice date (Date facture)\n"
        "- Supplier information (Information fournisseur: name and address, usually located at the top of the first page)\n"
        "- Number of packages (Nombre de colis)\n"
        "- Total price (Total: total_ht, tva, total_ttc, usually located at the end of the last page)\n\n"
        "2. Extract, clean, and reorder only the articles table information.\n"
        "For each article, map the columns as follows:\n"
        "- reference (should be a string or number)\n"
        "- designation (should be a string)\n"
        "- packaging (should be an integer)\n"
        "- quantite (should be an integer)\n"
        "- prix unitaire (should be a float, price in euros)\n"
        "- total (should be a float, price in euros)\n"
        "- brand (check in the designation if you find an existing brand, otherwise use null)\n"
        f"- category (attribute a category based on the designation, using only one of the following: {categories})\n"
        "For example, the first article row is mapped as:\n"
        f"{example_row}\n\n"
        "IMPORTANT: If you see identical or very similar consecutive rows in the invoice, preserve ALL of them. "
        "These represent multiple separate purchases of the same item and should NOT be deduplicated. "
        "Each row in the original invoice must appear exactly once in your output.\n\n"
        "Return a single valid JSON object with this structure:\n"
        "{\n"
        '  "Numéro de facture": ...,\n'
        '  "Date facture": ...,\n'
        '  "Information fournisseur": {"nom": ..., "adresse": ...},\n'
        '  "Nombre de colis": ...,\n'
        '  "Total": {"total_ht": ..., "tva": ..., "total_ttc": ...},\n'
        '  "articles": "<cleaned markdown table of articles, without header>"\n'
        "}\n"
        "Do not include any extra commentary or explanation."
    )
