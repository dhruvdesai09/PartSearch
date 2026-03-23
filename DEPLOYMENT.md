# Deploying the Voice Searchable Price List (frontend + backend + database)

This app has three parts that must work together:

| Part | Role | Typical host |
|------|------|----------------|
| **Database** | Postgres + `pg_trgm` | [Supabase](https://supabase.com) (or Neon, Railway Postgres, etc.) |
| **Backend** | FastAPI (`/upload`, `/search`) | [Render](https://render.com) or [Railway](https://railway.app) |
| **Frontend** | Vite + React | [Vercel](https://vercel.com) |

The browser loads the **frontend**. The frontend calls the **backend** using `VITE_API_BASE`. The backend uses **`DATABASE_URL`** to talk to Postgres.

---

## 0. Put the code on GitHub (or GitLab) first

Hosts like **Render** and **Vercel** do **not** deploy from a folder only on your PC. They deploy from a **remote Git repository**.

1. Create a repository on **GitHub** (empty, no README required, or with one).
2. In your project folder on your machine:

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

3. Confirm on github.com that `frontend/`, `backend/`, etc. are visible.

Until this exists, **Render will not list “this repo”**—there is nothing for Render to pull from.

---

## 1. Database (Supabase)

### Create the project

1. Go to [supabase.com](https://supabase.com) → New project → choose region and a strong DB password (save it).

### Connection string for this backend

The Python app uses **SQLAlchemy** with **`psycopg2`**. Your `DATABASE_URL` should look like:

```text
postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres
```

1. In Supabase: **Project Settings → Database**.
2. Copy the **URI** (or build it from host, user, password, port). Use the direct database connection (port **5432**) unless you switch to the pooler on purpose.
3. Replace `postgresql://` with `postgresql+psycopg2://` if the UI gives plain `postgresql://`.
4. URL-encode special characters in the password (e.g. `@` → `%40`).

### Security

- Never commit `DATABASE_URL` to Git. Use each platform’s **Environment Variables** UI.
- Supabase **Table Editor** is useful later to confirm rows after an upload.

### Extension

The backend runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` on startup (fuzzy search). That is allowed on Supabase Postgres.

---

## 2. Backend on Render (detailed)

### 2.1 If your repository does not show up on Render

Work through these in order:

1. **Repo only on your computer**  
   Push it to GitHub/GitLab first (see **§0**). Render lists **remote** repos, not local folders.

2. **Git provider not linked to Render**  
   - Log in to [dashboard.render.com](https://dashboard.render.com).  
   - **Account Settings** (your avatar) → find **GitHub** / **GitLab** / **Bitbucket** and click **Connect** (or **Configure**).  
   - Complete the OAuth flow in the browser.

3. **GitHub App permissions**  
   - On GitHub: **Settings → Applications → Authorized OAuth Apps** (or **Installed GitHub Apps**) → **Render**.  
   - Ensure Render has access to the **account or organization** that owns the repo.  
   - If you chose **“Only select repositories”**, add this repository to the list.

4. **Organization restrictions**  
   If the repo is under a **company/org**, an org owner may need to **approve** the Render GitHub App under the org’s third-party application settings.

5. **Wrong GitHub user**  
   You might be logged into Render with Google but GitHub with another account. Disconnect and reconnect the correct GitHub account on Render.

6. **Deploy without picking from the list (fallback)**  
   When creating a service, some flows allow **Public Git repository** and pasting:

   `https://github.com/YOUR_USERNAME/YOUR_REPO.git`  

   The repo must be **public**, or you must use the normal connected flow for private repos.

After fixing access, use **New → Web Service** and refresh the repository list.

### 2.2 Create a Web Service (Python / FastAPI)

1. **New +** → **Web Service** → select your repository.
2. **Name:** e.g. `price-list-api`.
3. **Region:** choose closest to your users.
4. **Branch:** `main` (or your default branch).
5. **Root Directory:** `backend`  

   This repo is a **monorepo** (`frontend/` and `backend/` side by side). Render must run commands **inside** `backend/` where `main.py` and `requirements.txt` live.

6. **Runtime:** Python 3 (pick **3.11** or **3.12** if offered).

7. **Build command:**

   ```bash
   pip install -r requirements.txt
   ```

8. **Start command:**

   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

   Render sets **`PORT`** automatically; do not hard-code `8000` in production.

9. **Instance type:** Free tier is fine to start; cold starts can add a few seconds after idle.

### 2.3 Environment variables on Render

In the service → **Environment**:

| Key | Required | Example / notes |
|-----|----------|------------------|
| `DATABASE_URL` | Yes | Full Supabase URL with `postgresql+psycopg2://...` |
| `OCR_ENABLED` | No | `false` on free tiers avoids needing Tesseract installed |
| `LOG_LEVEL` | No | `INFO` |
| `PRICE_MIN` | No | Minimum valid price for table parsing (default `100`) |
| `PRICE_MAX` | No | Maximum valid price to reject OCR false positives (default `100000`) |
| `FORMAT2_PRICE_MIN` | No | Minimum valid dual-column price for Format 2 (default `100`) |
| `FORMAT2_PRICE_MAX` | No | Maximum valid dual-column price for Format 2 (default `100000`) |
| `UPLOAD_DEBUG` | No | Set to `true` temporarily to return a small `sample` of parsed rows from `POST /upload` (useful for debugging price/case parsing). |

Click **Save** and trigger a **Manual Deploy** if the first build failed before variables were set.

### 2.4 After deploy

- Open `https://YOUR-SERVICE.onrender.com/health` — expect `{"ok": true}`.
- Copy the **exact** service URL (HTTPS). That is what you will put in `VITE_API_BASE` (no trailing slash).

### 2.5 Render quirks

- **Cold start:** Free web services sleep; first request after idle can take ~30–60+ seconds.
- **Build logs:** If the build fails, read the log: wrong **Root Directory** is the most common mistake for monorepos.

---

## 3. Backend on Railway (alternative)

Useful if you prefer a simpler Git connect flow or different pricing.

1. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → select the repo.
2. Add a **service** from the repo; set **Root Directory** to `backend`.
3. **Settings → Deploy → Custom Start Command:**

   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

   Railway injects `PORT`; check their docs if your template uses a different variable name.
4. **Variables:** add `DATABASE_URL` (same format as above).
5. Generate a **public URL** in **Networking** / **Settings** and use it for `VITE_API_BASE`.

---

## 4. Frontend on Vercel

1. [vercel.com](https://vercel.com) → **Add New… → Project** → **Import** your GitHub repository.
2. **Root Directory:** `frontend`  

   Click **Edit** next to the repo name and set the root to `frontend`, or Vercel will not find `package.json` correctly.

3. **Framework Preset:** Vite (auto-detected if root is correct).

4. **Build Command:** `npm run build` (default).

5. **Output Directory:** `dist` (Vite default).

6. **Environment Variables (Production):**

   | Name | Value |
   |------|--------|
   | `VITE_API_BASE` | `https://YOUR-BACKEND.onrender.com` (or Railway URL) — **no** trailing slash |

7. **Deploy.** Vite reads `VITE_*` variables at **build time**. If you change `VITE_API_BASE`, run **Redeploy** so the new URL is baked in.

8. Optional: add the same variable for **Preview** deployments if you use PR previews.

---

## 5. End-to-end checklist

1. Code is on **GitHub** (or GitLab) and Render/Vercel can see it after **Git provider** is connected.
2. **Supabase** project exists; `DATABASE_URL` is correct and **not** committed to Git.
3. **Render (or Railway)** service has **Root Directory** = `backend`, start command uses **`$PORT`**, and `/health` works over HTTPS.
4. **Vercel** has **Root Directory** = `frontend` and **`VITE_API_BASE`** matches the backend URL exactly.
5. Open the Vercel site, upload a PDF, then search — if errors mention “Cannot reach the API”, the URL or CORS is wrong.

---

## 6. CORS (production)

The backend must **not** combine `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials: true` — browsers **block** cross-origin responses, and the frontend will show **network errors** (e.g. failed PDF upload) even when the server is up.

This repo defaults to **`CORS_ORIGINS=*`** with **credentials disabled**, which is valid. To lock down production, set **`CORS_ORIGINS`** on Render to your Vercel origin(s), comma-separated, e.g. `https://your-app.vercel.app` (then credentials can be enabled in code for those origins only).

---

## 7. Local testing (all three)

- **Database:** Supabase connection string from your machine, or local Postgres.
- **Backend:** from `backend/`:

  ```bash
  set DATABASE_URL=postgresql+psycopg2://...
  uvicorn main:app --reload --port 8000
  ```

  (On PowerShell use `$env:DATABASE_URL="..."`.)

- **Frontend:** from `frontend/`:

  ```bash
  npm install
  npm run dev
  ```

  Optional: `frontend/.env` with `VITE_API_BASE=http://localhost:8000`.

---

## 8. Troubleshooting

### 8.1 Render + Supabase: `Network is unreachable` (IPv6)

If logs show something like:

```text
connection to server at "db.xxxxx.supabase.co" (2406:....), port 5432 failed: Network is unreachable
```

then the database hostname resolved to an **IPv6** address, and Render’s network path to that address failed. This is common with Supabase **direct** connections (`db.PROJECT.supabase.co:5432`).

**Fix (built into this repo):** the backend resolves the hostname to an **IPv4** address and appends **`hostaddr=<IPv4>`** to your `DATABASE_URL` query string (libpq reads this from the URI; passing `hostaddr` only via SQLAlchemy `connect_args` is unreliable on some stacks). It applies when the host is `*.supabase.co`, `*.pooler.supabase.com`, or `RENDER=true` / `DB_FORCE_IPV4=true`. **Redeploy** the backend after pulling the latest `main.py`.

**If you still see errors:**

- Set **`DB_FORCE_IPV4=true`** in Render → Environment (explicit opt-in).
- Or switch **`DATABASE_URL`** in Render to Supabase’s **connection pooler** (Supabase Dashboard → **Project Settings → Database** → *Connection pooling* / *Session pooler*). Use the URI they give for port **6543** and the pooler host, with `sslmode=require` if shown. Adjust the scheme to `postgresql+psycopg2://` for this app.

**Optional:** set **`DB_FORCE_IPV4=false`** only if you must use IPv6 end-to-end (rare on PaaS).

### 8.2 Quick reference

| Symptom | What to check |
|--------|----------------|
| Render does not show my repo | Repo pushed to GitHub? Render **connected** to GitHub? App allowed for org/private repo? |
| Build fails: `requirements.txt` not found | **Root Directory** must be `backend`. |
| Supabase IPv6 “Network is unreachable” on Render | See **§8.1**; redeploy backend with IPv4 fix or use pooler URL. |
| Backend crashes on start | `DATABASE_URL` missing/wrong; password special chars URL-encoded; Supabase project paused. |
| Frontend: “Cannot reach the API” | `VITE_API_BASE` wrong; backend asleep (wait and retry); mixed `http`/`https`. |
| CORS error in browser | Backend `allow_origins`; frontend URL must match what you allow. |
| Upload/search “network” error but `/health` works | Was often **`*` + credentials** (fixed in `main.py`). Redeploy backend; set `CORS_ORIGINS` if needed. |
| Search always empty | Upload succeeded? Check Supabase **Table Editor** for `products` rows. |
| Wrong prices / missing certain parts | Parsing guardrails may be too strict or the PDF layout is noisy. Check backend env `PRICE_MIN/PRICE_MAX` and `FORMAT2_PRICE_MIN/FORMAT2_PRICE_MAX` (and redeploy). Numeric-only part numbers are supported, but OCR/table extraction quality can still affect which rows are recognized. |

---

## 9. Optional: Blueprint (`render.yaml`)

If you use Render **Blueprints**, you can define the web service in-repo. This is optional; the manual UI steps above are enough. If you add a `render.yaml`, keep **root directory** and commands aligned with the `backend/` folder as in **§2.2**.

---

You now have a path from **local folder → GitHub → Render + Vercel + Supabase** with explicit fixes for the common “Render doesn’t show my repository” case (remote repo + linked Git provider + app permissions).
