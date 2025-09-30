# Invoice Analyst Platform

Modernised architecture for the Invoice Analyst application, featuring a FastAPI backend for AI-powered invoice processing and a Next.js frontend for a polished user experience.

## Stack Overview

- **Backend**: FastAPI application (`backend/app`) wrapping the existing OCR, AI extraction, and Supabase persistence logic.
- **Shared Python Library**: Reusable domain, adapter, and service modules under `src/invoice_analyst`.
- **Frontend**: Next.js 14 application (`apps/web`) with Supabase authentication, extraction workflow, analytics dashboard, and management screens.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase project with the existing schema
- Mistral API credentials

## Environment Variables

Create a `.env` file at the project root for the backend:

```bash
SUPABASE_URL=...            # Supabase project URL
SUPABASE_KEY=...            # Service role key (used server-side)
MISTRAL_API_KEY=...         # Mistral API key
SUPABASE_INVOICES_BUCKET=invoices
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:3001  # comma-separated list of frontend origins
```

Create an `.env.local` inside `apps/web/` for the frontend:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

## Backend Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn backend.app.main:app --reload --port 8000
```

The FastAPI service exposes:

- `POST /api/extract` – OCR + AI structuring + annotated PDF storage
- `POST /api/invoices` – Persist invoices, products, and totals
- `POST /api/invoices/delete` – Bulk deletion with storage cleanup
- `POST /api/invoices/download` – Zip archive generation for selected invoices
- `GET /health` – Health check endpoint

## Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

The web app runs on <http://localhost:3000> and mirrors the original UX:

- **Authentication**: Supabase email/password login
- **Extraction**: PDF upload, AI extraction, interactive corrections, and persistence
- **Dashboard**: Global spending charts, supplier insights, product leaders
- **Gestion**: Invoice management (view/delete/download) and product overview

## Project Structure

```
.
├── backend/
│   └── app/               # FastAPI app and routers
├── src/invoice_analyst/   # Shared Python domain/adapters/services
│   ├── domain/            # Models, constants, prompts
│   ├── adapters/          # External services (Mistral, Supabase, PDF)
│   ├── services/          # Business logic (extraction, persistence)
│   └── logging_config.py  # Application logging
├── apps/web/              # Next.js frontend
├── docs/                  # Documentation
│   ├── architecture.md
│   └── CLAUDE.md
├── pyproject.toml         # Python package config & dependencies
└── README.md
```

## Development Notes

- The domain logic is framework-agnostic and lives under `src/invoice_analyst`.
- Use `NEXT_PUBLIC_API_BASE_URL` to point the frontend to remote environments.
- Supabase Row Level Security should remain enabled; all queries filter by the authenticated user.
- The application uses structured logging via `invoice_analyst.logging_config`.
- Code formatting: Use `black .` and linting: `flake8 .` (configured in pyproject.toml).

## Next Steps

- Expand anomaly detection visuals on the dashboard
- Add rich editing for product catalog management
- Introduce end-to-end tests for extraction flows
