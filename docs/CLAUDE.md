# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack & Architecture

This is a **modernized invoice analysis platform** with:
- **Backend**: FastAPI application (`backend/app`) exposing REST APIs
- **Shared Python Library**: Framework-agnostic business logic in `src/invoice_analyst/` organized as:
  - `domain/`: Core models, constants
  - `adapters/`: External service wrappers (Mistral AI, Supabase, PDF processing)
  - `services/`: Business logic (extraction, persistence, storage)
- **Frontend**: Next.js 14 application (`apps/web`) with Supabase auth and analytics
- **Legacy**: Original Streamlit app preserved in `legacy/streamlit/`

**Key principle**: Business logic is framework-agnostic and reusable; FastAPI and Next.js are thin layers.

## Development Commands

### Backend

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Development
uvicorn backend.app.main:app --reload --port 8000

# Install dev dependencies
pip install -e ".[dev]"

# Code quality
black .
flake8 .
pytest  # (no tests currently exist)
```

**Environment**: Create `.env` at project root:
```bash
SUPABASE_URL=...
SUPABASE_KEY=...                    # Service role key
MISTRAL_API_KEY=...
SUPABASE_INVOICES_BUCKET=invoices
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:3001
```

### Frontend

```bash
cd apps/web
npm install
npm run dev      # Development server on :3000
npm run build    # Production build
npm run lint     # ESLint
```

**Environment**: Create `apps/web/.env.local`:
```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...   # Anon/public key
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

## API Endpoints

- `GET /health` – Health check
- `POST /api/extract` – Upload PDF, run OCR + AI extraction, get annotated PDF + structured data
- `POST /api/invoices` – Persist invoice with products to Supabase
- `POST /api/invoices/delete` – Bulk delete with storage cleanup
- `POST /api/invoices/download` – Generate zip archive of selected invoices

## Extraction Pipeline Architecture

The invoice extraction flow is the core of this application:

### 1. **OCR Extraction** (`MistralAdapter.extract_markdown`)
- Uploads PDF to Mistral AI's OCR service
- Returns markdown with embedded base64 images
- Combines multi-page results into single markdown string

### 2. **AI Structuring** (`MistralAdapter.structure`)
- Takes OCR markdown + few-shot prompt with example row
- Uses `pixtral-12b-latest` with JSON mode (temperature=0)
- Returns structured JSON with invoice metadata + articles table

### 3. **Article Parsing** (`services/extraction.py:_parse_articles`)
- Handles three formats: list of dicts, list of tuples, markdown table string
- Validates with Pydantic `Article` model
- Maps French field names (aliases) to Python attributes

### 4. **PDF Annotation** (`pdf_annotator.highlight_pdf`)
- For each article, finds matching line in PDF using reference text
- Uses fuzzy matching (`difflib.SequenceMatcher` with 0.85 threshold) + float comparison
- Highlights in **green** if all fields found, **red** if missing fields detected
- Adds hover annotations listing missing fields

### 5. **Validation Status** (`services/extraction.py:_add_validation_status`)
- After PDF annotation, re-parses each article line
- Calls `_find_missing_values` to check if all article fields appear in PDF text
- Adds `validationStatus: "correct"|"error"` and `missingFields: [...]` to response
- **Critical**: This allows frontend to highlight table rows matching PDF colors

### 6. **Return**
Returns `ExtractionResult` with:
- `structured`: Invoice metadata (number, date, supplier, totals)
- `articles`: List of articles with validation metadata
- `annotatedPdfBase64`: Highlighted PDF for user review

## Database Persistence Layer

The `persist_invoice` function orchestrates a **get-or-create pattern** for related entities:

1. **Supplier** (`fournisseurs` table): Match by `user_id + nom`, update address if exists
2. **Invoice** (`factures` table): Match by `user_id + fournisseur_id + numero`, upsert
3. **For each article**:
   - **Category** (`categories` table): Match by `user_id + nom`
   - **Brand** (`marques` table): Match by `user_id + nom`
   - **Product** (`produits` table): Match by `user_id + reference + fournisseur_id`
   - **Invoice Line** (`lignes_facture` table): Insert with foreign keys

**Important**: All queries filter by `user_id` (multi-tenant via Supabase RLS).

**Storage**: PDFs stored in Supabase storage as `{user_id}/{invoice_id}_{filename}`.

## Key Patterns & Conventions

### Pydantic Models with Aliases
Models in `domain/models.py` use `alias` to map French API/DB names to Python attributes:
```python
class Article(BaseModel):
    reference: Optional[str] = Field(alias="Reference", default=None)
    unit_price: Optional[float] = Field(alias="Prix Unitaire", default=None, ge=0)
    validation_status: Optional[str] = Field(alias="validationStatus", default=None)

    class Config:
        populate_by_name = True  # Accept both names
```
Use `.model_dump(by_alias=True)` when returning to frontend.

### Dependency Injection
FastAPI dependencies in `backend/app/config.py`:
```python
def get_supabase() -> Client:
    return get_supabase_client(...)

@router.post("/extract")
async def run_extraction(supabase=Depends(get_supabase), ...):
    ...
```
Uses `@lru_cache` on `get_settings()` to avoid re-reading env vars.

### Validation Status Integration
The extraction service adds validation metadata that **must match PDF annotation colors**:
- **Green** (`validationStatus: "correct"`): All fields found in PDF
- **Red** (`validationStatus: "error"`): Missing fields, listed in `missingFields: ["Prix Unitaire", ...]`

This synchronization is documented in `apps/web/BACKEND_INTEGRATION.md`.

### Fuzzy Matching Logic
`_find_missing_values` in `pdf_annotator.py`:
- Splits PDF line text into tokens
- For each article field value, searches tokens with fuzzy match (85% ratio) or float equality
- Returns list of fields not found
- **Used twice**: Once for PDF annotation color, once for response metadata

## Important Files

- `backend/app/main.py`: FastAPI app factory with CORS
- `backend/app/routers/extraction.py`: Extraction endpoint
- `backend/app/routers/invoices.py`: Persistence, deletion, download endpoints
- `src/invoice_analyst/services/extraction.py`: Core extraction orchestration
- `src/invoice_analyst/services/persistence.py`: Database upsert logic
- `src/invoice_analyst/adapters/mistral_client.py`: Mistral AI SDK wrapper
- `src/invoice_analyst/adapters/pdf_annotator.py`: PyMuPDF highlighting + validation
- `src/invoice_analyst/domain/models.py`: Pydantic schemas
- `src/invoice_analyst/domain/constants.py`: Article columns, categories

## Supabase Schema (Inferred)

Tables used (all filtered by `user_id`):
- `fournisseurs`: id, user_id, nom, adresse
- `factures`: id, user_id, fournisseur_id, numero, date, nom_fichier, total_ht, tva_amount, total_ttc, nombre_colis
- `categories`: id, user_id, nom
- `marques`: id, user_id, nom
- `produits`: id, user_id, reference, designation, fournisseur_id, categorie_id, marque_id
- `lignes_facture`: id, user_id, facture_id, produit_id, prix_unitaire, collisage, quantite, montant

Storage bucket: `invoices` (configured via `SUPABASE_INVOICES_BUCKET`)