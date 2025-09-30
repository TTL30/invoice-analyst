# Backend Integration for Article Validation Highlighting

## Overview
The frontend now supports highlighting table rows with the same colors used in PDF annotations:
- **Green background** (`bg-green-50`): Article validated correctly
- **Red background** (`bg-red-50`): Article has missing or incorrect values

## Required Backend Changes

### 1. Update Article Response Structure

When returning extracted articles, include validation metadata for each article:

```python
# In your extraction response
{
  "structured": {...},
  "articles": [
    {
      "Reference": "REF001",
      "Désignation": "Product Name",
      "Prix Unitaire": 10.5,
      "Packaging": 6,
      "Quantité": 2,
      "Total": 21.0,
      "Marque": "BrandX",
      "Catégorie": "CategoryA",
      # ADD THESE FIELDS:
      "validationStatus": "correct",  # or "error" or null
      "missingFields": null  # or ["Prix Unitaire", "Total"] for errors
    },
    {
      "Reference": "REF002",
      # ... other fields ...
      "validationStatus": "error",
      "missingFields": ["Prix Unitaire", "Total"]  # Fields that couldn't be found/validated
    }
  ],
  "annotatedPdfBase64": "...",
  "fileName": "..."
}
```

### 2. Determine Validation Status

Use the same logic from `pdf_annotator.py`:

```python
from invoice_analyst.adapters.pdf_annotator import _find_missing_values

def add_validation_status(article: dict, pdf_line_text: str) -> dict:
    """Add validationStatus and missingFields to article based on PDF analysis."""

    # Extract just the data fields for validation
    article_data = {
        k: v for k, v in article.items()
        if k not in ["validationStatus", "missingFields"]
    }

    # Use the same logic as PDF annotator
    missing = _find_missing_values(pdf_line_text, article_data)

    if missing:
        article["validationStatus"] = "error"
        article["missingFields"] = [key for key, _ in missing]
    else:
        article["validationStatus"] = "correct"
        article["missingFields"] = None

    return article
```

### 3. Integration Point

Update your extraction endpoint (likely in your FastAPI/Flask backend):

```python
# In your extraction logic
for i, article in enumerate(extracted_articles):
    # Get the corresponding PDF line text that was annotated
    pdf_line_text = get_pdf_line_for_article(pdf_doc, article)

    # Add validation status
    article = add_validation_status(article, pdf_line_text)

    extracted_articles[i] = article

return {
    "structured": structured_data,
    "articles": extracted_articles,
    "annotatedPdfBase64": annotated_pdf_base64,
    "fileName": filename
}
```

## Color Mapping

The colors match the PDF annotation logic:
- PDF: `color = (0.0, 0.5, 0.0)` with opacity 0.2 → Frontend: `bg-green-50`
- PDF: `color = (1.0, 0.0, 0.0)` with opacity 0.2 → Frontend: `bg-red-50`

## Testing

To test without backend changes, you can temporarily add validation data in the frontend:

```typescript
// In ExtractionSteps.tsx, after receiving result
const articlesWithValidation = result.articles.map((article, index) => ({
  ...article,
  validationStatus: index === 0 ? "correct" : (Math.random() > 0.7 ? "error" : "correct"),
  missingFields: index === 1 ? ["Prix Unitaire"] : null
}));
setArticles(articlesWithValidation);
```

## Benefits

1. **Visual Consistency**: Table rows match PDF highlights
2. **Error Detection**: Users can see which rows have issues at a glance
3. **Debugging Info**: Hovering over red rows shows which fields are problematic
4. **Trust Building**: Users can verify the AI extraction quality immediately