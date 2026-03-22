# Deploying the Voice Searchable Price List (frontend + backend + database)

This project has three moving parts: a **Postgres** database (recommended: Supabase), a **FastAPI** backend (Railway or Render), and a **Vite/React** frontend (Vercel). The browser talks only to the frontend; the frontend calls the backend with `VITE_API_BASE`.

---

## 1. Database (Supabase)

1. Create a project at [supabase.com](https://supabase.com).
2. In **Project Settings → Database**, copy the **URI** connection string (use the **Transaction** or **Session** pooler if you prefer; the backend uses SQLAlchemy with `psycopg2`).
3. Convert the URL for SQLAlchemy if needed. The backend expects a URL like:

   `postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres`

   Replace `USER`, `PASSWORD`, `HOST`, and database name with what Supabase shows (often port `5432` or pooler port `6543`).

4. The app runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` on startup (used for fuzzy search). Supabase allows this on Postgres.

5. Keep this string secret; you will paste it into the backend host as `DATABASE_URL`.

---

## 2. Backend (Railway or Render)

**What you need**

- Root directory: `backend/` (or set the service root to that folder).
- **Start command** (example):

  `uvicorn main:app --host 0.0.0.0 --port $PORT`

  Use `$PORT` on Render; on Railway, check their docs (often `PORT` is set automatically).

- **Python version**: match what you use locally (e.g. 3.11+). Install dependencies from `backend/requirements.txt`.

**Environment variables**

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | Yes | Same as Supabase URI, SQLAlchemy form (`postgresql+psycopg2://...`). |
| `OCR_ENABLED` | No | `true`/`false`; OCR needs Tesseract on the server (extra setup on Railway/Render). |
| `TESSERACT_CMD` | No | Path to `tesseract` binary if not on `PATH`. |
| `LOG_LEVEL` | No | e.g. `INFO` |

**CORS**

The API currently allows all origins (`allow_origins=["*"]`). For production, narrow this in `backend/main.py` to your Vercel domain (e.g. `https://your-app.vercel.app`) so only your frontend can call the API.

**Health check**

After deploy, open `https://YOUR-BACKEND/health` — you should see `{"ok": true}`.

**Upload/search**

- `POST /upload` — multipart field `file` (PDF).
- `GET /search?q=...` — search.

---

## 3. Frontend (Vercel)

1. Connect the repo (or deploy the `frontend/` folder).
2. **Build command:** `npm run build`
3. **Output directory:** `dist`
4. **Environment variable (production):**

   `VITE_API_BASE` = `https://YOUR-BACKEND-HOST`  

   No trailing slash. Example: `https://price-api.up.railway.app`

   Vite bakes this in at **build time**, so change the variable and **redeploy** the frontend whenever the API URL changes.

5. Deploy. Open the Vercel URL; upload and search should hit your hosted API.

---

## 4. Wiring the three together (checklist)

1. Supabase Postgres is up; `DATABASE_URL` works from your machine with `psql` or a quick Python test.
2. Backend deployed; `/health` returns OK.
3. `DATABASE_URL` set on the backend service; logs show DB init without fatal errors.
4. `VITE_API_BASE` on Vercel points exactly to the backend base URL (scheme + host, no path).
5. Frontend redeployed after setting `VITE_API_BASE`.
6. Optional: restrict CORS on the backend to the Vercel URL.

---

## 5. Local testing (all three)

- Run Postgres locally or use Supabase from your PC.
- Backend: `DATABASE_URL=... uvicorn main:app --reload --port 8000` from `backend/`.
- Frontend: `npm run dev` in `frontend/` (default API `http://localhost:8000` if `VITE_API_BASE` is unset).

---

## 6. Common failures

| Symptom | What to check |
|--------|----------------|
| Upload/search: “Cannot reach the API” | Backend URL wrong, backend down, or mixed HTTP/HTTPS (use HTTPS everywhere in prod). |
| Backend 500 on startup | `DATABASE_URL` wrong, DB not reachable from Railway/Render IP (Supabase usually allows this). |
| Search always empty | PDF imported OK? Run a query that matches data; check DB in Supabase **Table Editor**. |
| CORS errors in browser | Add your Vercel origin to FastAPI `allow_origins` or temporarily use `*` for debugging only. |

This should be enough to get a stable end-to-end deployment on free/low-cost tiers; tune OCR and CORS once the happy path works.
