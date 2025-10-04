"""Template detection and matching."""

import re
import yaml
from pathlib import Path
from typing import List, Optional
from invoice_analyst.extraction.pdfextract.models import (
    Template,
    TableConfig,
    TextBlock,
    ColumnVariant,
)


def load_template(template_path: str) -> Template:
    """Load and validate YAML template.

    Args:
        template_path: Path to YAML template file

    Returns:
        Validated Template object

    Raises:
        FileNotFoundError: If template file not found
        ValueError: If template structure is invalid
    """
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse YAML template: {e}")

    required_fields = ["supplier", "identifiers", "table"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    table_data = data["table"]
    required_table_fields = ["start_anchor", "header_rows", "header"]
    for field in required_table_fields:
        if field not in table_data:
            raise ValueError(f"Missing required table field: {field}")

    # Parse column offset variants if present
    variants = None
    if "column_offset_variants" in table_data:
        variants = []
        for variant_data in table_data["column_offset_variants"]:
            variants.append(
                ColumnVariant(
                    offsets=variant_data["offsets"], detect_pattern=variant_data["detect_pattern"]
                )
            )

    table_config = TableConfig(
        start_anchor=table_data["start_anchor"],
        header_rows=table_data["header_rows"],
        header=table_data["header"],
        end_anchor=table_data.get("end_anchor"),
        footer_keywords=table_data.get("footer_keywords"),
        summary_patterns=table_data.get("summary_patterns"),
        detail_patterns=table_data.get("detail_patterns"),
        skip_chars=table_data.get("skip_chars"),
        use_data_driven_boundaries=table_data.get("use_data_driven_boundaries", False),
        min_aligned_blocks=table_data.get("min_aligned_blocks", 2),
        alignment_threshold=table_data.get("alignment_threshold", 0.3),
        column_char_offsets=table_data.get("column_char_offsets"),
        column_offset_variants=variants,
        excluded_columns=table_data.get("excluded_columns"),
    )

    return Template(
        supplier=data["supplier"],
        identifiers=data["identifiers"],
        table=table_config,
    )


def find_matching_template(blocks: List[TextBlock], template: Template) -> bool:
    """Check if PDF matches template using identifier patterns.

    Args:
        blocks: List of text blocks from PDF
        template: Template to match against

    Returns:
        True if all identifiers found in PDF text
    """
    all_text = " ".join(block.text for block in blocks)

    for identifier in template.identifiers:
        if not re.search(identifier, all_text, re.IGNORECASE):
            return False

    return True


def discover_templates(templates_dir: str = "templates") -> List[Path]:
    """Discover all YAML template files in templates directory.

    Args:
        templates_dir: Path to templates directory (default: "templates")

    Returns:
        List of Path objects for all .yaml files found

    Raises:
        FileNotFoundError: If templates directory does not exist
    """
    templates_path = Path(templates_dir)

    if not templates_path.exists():
        raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

    return list(templates_path.glob("*.yaml"))


def find_matching_template_from_directory(
    blocks: List[TextBlock], templates_dir: str = "templates"
) -> Optional[Template]:
    """Find first matching template from templates directory.

    Args:
        blocks: List of text blocks from PDF
        templates_dir: Path to templates directory (default: "templates")

    Returns:
        First matching Template object, or None if no match found

    Raises:
        FileNotFoundError: If templates directory does not exist
    """
    template_files = discover_templates(templates_dir)

    for template_file in template_files:
        try:
            template = load_template(str(template_file))
            if find_matching_template(blocks, template):
                return template
        except Exception as e:
            print(f"Warning: Failed to load template {template_file}: {e}")
            continue

    return None
