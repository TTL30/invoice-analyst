# Architecture Overview

## Backend (FastAPI)
- **Entry point**: `backend/app/main.py`
- **Routers**: `extraction`, `invoices`
- **Configuration**: `backend/app/config.py` loads Supabase + Mistral settings and allowed CORS origins from environment variables
- **Domain Services** (reused across routers):
  - `src/invoice_analyst/adapters/` – Mistral client wrapper, Supabase helper, PDF annotation utilities
  - `src/invoice_analyst/services/` – Extraction orchestration, persistence layer, storage helper
  - `src/invoice_analyst/domain/` – Pydantic models and constants used across the stack

## Frontend (Next.js)
- Located in `apps/web`
- Uses Supabase for authentication (`hooks/useSupabase` + context provider)
- Key feature areas:
  - `app/(protected)/extract` → Extraction workflow (`ExtractionWorkspace`)
  - `app/(protected)/dashboard` → Analytics dashboard (`DashboardTabs`)
  - `app/(protected)/gestion` → Invoice & product management (`GestionWorkspace`)
- Shared UI components under `components/`
- API helpers under `lib/api/`

## Legacy Streamlit App
Moved to `legacy/streamlit` for historical reference; no longer part of the runtime path.

## Data Flow
1. **Upload & Extraction**
   - Frontend posts PDF + confirmation row to `POST /api/extract`
   - Backend stores temporary PDFs, runs Mistral OCR/LLM, highlights PDF, returns structured payload
2. **Review & Save**
   - User edits metadata in the frontend and sends it to `POST /api/invoices`
   - Backend normalises suppliers, products, categories, uploads final PDF, and writes invoice lines
3. **Analytics & Management**
   - Frontend queries Supabase directly for dashboards and management tables
   - Destructive actions (delete, download) go through backend helpers to keep storage and data consistent
