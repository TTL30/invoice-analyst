"""Mistral API integration for structured invoice data extraction."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from mistralai import Mistral


class MistralExtractor:
    """Extracts structured JSON data from invoice markdown using Mistral API."""

    def __init__(self, api_key: str):
        """Initialize Mistral client with API key.

        Args:
            api_key: Mistral API key for authentication
        """
        self.client = Mistral(api_key=api_key)
        self.model = "mistral-large-latest"
        self.max_retries = 3
        self.base_delay = 2  # seconds

    def load_prompt_template(self, template_path: Path) -> str:
        """Load prompt template from file.

        Args:
            template_path: Path to prompt template file

        Returns:
            Prompt template content

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
        return template_path.read_text()

    def format_prompt(
        self,
        template: str,
        info_markdown: str,
        table_markdown: str,
        known_brands: list[str],
        known_categories: list[str],
    ) -> str:
        """Format prompt template with markdown inputs and database context.

        Args:
            template: Prompt template string with placeholders
            info_markdown: Invoice metadata markdown
            table_markdown: Articles table markdown
            known_brands: List of known brand names from database
            known_categories: List of known category names from database

        Returns:
            Formatted prompt ready for LLM
        """
        brands_text = ", ".join(known_brands) if known_brands else "None"
        categories_text = ", ".join(known_categories) if known_categories else "None"

        return template.format(
            info_markdown=info_markdown,
            table_markdown=table_markdown,
            known_brands=brands_text,
            known_categories=categories_text,
        )

    def extract_json(
        self,
        info_markdown: str,
        table_markdown: str,
        prompt_path: Path,
        known_brands: list[str] | None = None,
        known_categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Extract structured JSON from invoice markdown data.

        Uses Mistral API with retry logic and exponential backoff for rate limiting.
        Handles partial extraction by returning nullable fields.

        Args:
            info_markdown: Invoice metadata markdown
            table_markdown: Articles table markdown
            prompt_path: Path to prompt template file
            known_brands: List of known brand names from database
            known_categories: List of known category names from database

        Returns:
            Extracted invoice data as dictionary

        Raises:
            Exception: If extraction fails after all retries
        """
        # Load and format prompt
        template = self.load_prompt_template(prompt_path)
        prompt = self.format_prompt(
            template,
            info_markdown,
            table_markdown,
            known_brands or [],
            known_categories or [],
        )
        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.complete(
                    model=self.model, messages=[{"role": "user", "content": prompt}]
                )

                # Extract response content
                content = response.choices[0].message.content
                # Parse JSON response
                extracted_data = self._parse_json_response(content)
                return extracted_data

            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    print(f"Extraction attempt {attempt + 1} failed: {e}")
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"Extraction failed after {self.max_retries} attempts")

        raise Exception(
            f"Failed to extract data after {self.max_retries} retries: {last_exception}"
        )

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response and validate JSON structure.

        Handles cases where LLM might return JSON wrapped in markdown code blocks.

        Args:
            content: Raw LLM response content

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        # Remove markdown code blocks if present
        content = content.strip()

        # Strip opening code fence
        if content.startswith("```json"):
            content = content[7:].lstrip()
        elif content.startswith("```"):
            content = content[3:].lstrip()

        # Strip closing code fence
        if content.endswith("```"):
            content = content[:-3].rstrip()

        content = content.strip()

        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nContent: {content}")
