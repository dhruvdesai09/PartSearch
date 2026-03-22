# Backend (FastAPI)

## Endpoints
- `POST /upload` (multipart form): upload a PDF
  - form fields:
    - `file` (PDF)
    - `source_file` (optional)
- `GET /search?q=`: search by part number (typeahead / fuzzy)

## Required environment
- `DATABASE_URL` (Supabase Postgres / Railway / Render Postgres)

## OCR
OCR uses `pytesseract` and requires the Tesseract binary installed on the host.
Set `OCR_ENABLED=false` to disable.

