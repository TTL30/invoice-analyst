"""CLI for PDF extraction."""

import json
import sys
from pathlib import Path
from invoice_analyst.extraction.pdfextract.parser import extract_text_blocks
from invoice_analyst.extraction.pdfextract.detector import load_template, find_matching_template
from invoice_analyst.extraction.pdfextract.table_merger import extract_and_merge_tables
from invoice_analyst.extraction.pdfextract.markdown_generator import (
    generate_markdown,
    generate_info_markdown,
)
from invoice_analyst.extraction.pdfextract.utils import filter_non_table_blocks, deduplicate_blocks
from invoice_analyst.extraction.pdfextract.mistral_extractor import MistralExtractor
from invoice_analyst.extraction.pdfextract.pdf_annotator import annotate_pdf


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 4:
        print(
            "Usage: python -m pdfextract.cli <pdf_path> <template_path> <output_dir> [mistral_key] [--annotate]"
        )
        sys.exit(1)

    pdf_path = sys.argv[1]
    template_path = sys.argv[2]
    output_dir = Path(sys.argv[3])

    # Parse optional arguments
    mistral_key = None
    annotate_flag = False

    for arg in sys.argv[4:]:
        if arg == "--annotate":
            annotate_flag = True
        else:
            mistral_key = arg

    if not Path(pdf_path).exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    if not Path(template_path).exists():
        print(f"Error: Template file not found: {template_path}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        template = load_template(template_path)
        print(f"Loaded template for: {template.supplier}")

        blocks = extract_text_blocks(pdf_path)
        print(f"Extracted {len(blocks)} text blocks from PDF")

        if not find_matching_template(blocks, template):
            print("Warning: PDF does not match template identifiers")

        # Extract and merge tables
        try:
            merged_table, detected_tables = extract_and_merge_tables(blocks, template)
            print(f"Found table with {len(merged_table.rows)} rows across pages")

            # Generate table markdown with excluded columns
            excluded_columns = template.table.excluded_columns or []
            table_markdown = generate_markdown(merged_table, excluded_columns=excluded_columns)
        except ValueError as e:
            # No tables found - create empty table
            print(f"Warning: {e}")
            table_markdown = ""
            detected_tables = []

        # Filter non-table blocks
        info_blocks = filter_non_table_blocks(blocks, detected_tables)
        print(f"Found {len(info_blocks)} non-table text blocks")

        # Deduplicate info blocks
        deduplicated_info = deduplicate_blocks(info_blocks)
        print(f"After deduplication: {len(deduplicated_info)} unique info blocks")

        # Generate info markdown
        info_markdown = generate_info_markdown(deduplicated_info)

        # Write output files
        table_path = output_dir / "table.md"
        info_path = output_dir / "info.md"

        table_path.write_text(table_markdown)
        info_path.write_text(info_markdown)

        print(f"\n✓ Generated: {table_path}")
        print(f"✓ Generated: {info_path}")

        # Extract JSON using Mistral API if key provided
        invoice_data = None
        if mistral_key:
            try:
                print("\nExtracting structured data with Mistral API...")
                extractor = MistralExtractor(mistral_key)
                # Get prompt template path
                prompt_path = Path(__file__).parent.parent / "prompts" / "invoice_extraction.txt"

                # Extract JSON data
                invoice_data = extractor.extract_json(info_markdown, table_markdown, prompt_path)

                # Write JSON output
                json_path = output_dir / "invoice.json"
                json_path.write_text(json.dumps(invoice_data, indent=2, ensure_ascii=False))

                print(f"✓ Generated: {json_path}")
                print(f"  - Extracted {len(invoice_data.get('articles', []))} articles")

            except Exception as e:
                print(f"Warning: JSON extraction failed: {e}")
                print("Markdown files were still generated successfully")
        else:
            print("\n⊘ Skipping JSON extraction (no Mistral API key provided)")

        # Annotate PDF if flag provided and JSON extraction succeeded
        if annotate_flag and invoice_data:
            try:
                print("\nAnnotating PDF with validation highlights...")
                annotated_path = output_dir / f"{Path(pdf_path).stem}_annotated.pdf"
                annotated_bytes = annotate_pdf(pdf_path, invoice_data)
                annotated_path.write_bytes(annotated_bytes)
                print(f"✓ Generated: {annotated_path}")
            except Exception as e:
                print(f"Warning: PDF annotation failed: {e}")
        elif annotate_flag and not invoice_data:
            print("\n⊘ Skipping PDF annotation (no JSON data available)")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
