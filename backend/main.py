import os
import re
import socket
import uuid
import logging
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pdfplumber
import pytesseract
import regex as regex_lib
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from sqlalchemy import DateTime, Integer, String, Text, create_engine, text, func
from sqlalchemy.engine.url import make_url
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("price-search")


DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    logger.warning("DATABASE_URL is not set. Backend endpoints will fail until configured.")


def _append_url_query_param(url: str, key: str, value: str) -> str:
    """Merge a query parameter into a SQLAlchemy / libpq URL (preserves postgresql+psycopg2)."""
    p = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != key]
    pairs.append((key, value))
    new_query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def _effective_database_url(database_url: str) -> str:
    """
    Supabase hostnames often resolve to IPv6 first. Some PaaS networks (e.g. Render)
    cannot reach that path ("Network is unreachable").

    libpq honors `hostaddr` in the connection URI query string; SQLAlchemy's
    `connect_args={"hostaddr": ...}` alone is not always applied, so we embed
    `hostaddr=<IPv4>` in the URL.

    Set DB_FORCE_IPV4=false to disable. Otherwise IPv4 is used when RENDER=true, or the
    host is *.supabase.co / *.pooler.supabase.com, or DB_FORCE_IPV4=true.
    """
    flag = os.getenv("DB_FORCE_IPV4", "").strip().lower()
    if flag in ("0", "false", "no"):
        return database_url
    try:
        u = make_url(database_url)
    except Exception:
        return database_url
    host = u.host or ""
    if not host or host in ("localhost", "127.0.0.1"):
        return database_url
    should_force = (
        flag in ("1", "true", "yes")
        or os.getenv("RENDER") == "true"
        or host.endswith(".supabase.co")
        or "pooler.supabase.com" in host
    )
    if not should_force:
        return database_url
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        if not infos:
            return database_url
        ipv4 = infos[0][4][0]
        logger.info("Embedding IPv4 hostaddr for DB host %s -> %s", host, ipv4)
        return _append_url_query_param(database_url, "hostaddr", ipv4)
    except OSError as e:
        logger.warning("Could not resolve IPv4 for DB host %s: %s", host, e)
        return database_url

# Ensure pytesseract can find the tesseract binary even when PATH isn't updated.
_tesseract_cmd_env = os.getenv("TESSERACT_CMD")
_tesseract_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if _tesseract_cmd_env:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd_env
elif os.path.exists(_tesseract_default):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_default


class Base(DeclarativeBase):
    pass


class _ProductBase:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    designation: Mapped[str] = mapped_column(String, nullable=False)
    normalized_designation: Mapped[str] = mapped_column(
        String, unique=True, nullable=False
    )
    contents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pack_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    case_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AutomotiveProduct(_ProductBase, Base):
    __tablename__ = "automotive_products"


class IndustrialProduct(_ProductBase, Base):
    __tablename__ = "industrial_products"


_EFFECTIVE_DB_URL = _effective_database_url(DATABASE_URL) if DATABASE_URL else ""

if _EFFECTIVE_DB_URL:
    try:
        # Log only host/hostaddr (mask credentials); helps confirm the IPv4 override is active.
        u_eff = make_url(_EFFECTIVE_DB_URL)
        q = dict(parse_qsl(urlparse(_EFFECTIVE_DB_URL).query, keep_blank_values=True))
        logger.info(
            "DB effective host=%s hostaddr=%s port=%s",
            u_eff.host,
            q.get("hostaddr"),
            u_eff.port,
        )
    except Exception:
        logger.info("DB effective URL computed (could not parse hostaddr for logging).")

engine = (
    create_engine(
        _EFFECTIVE_DB_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    )
    if _EFFECTIVE_DB_URL
    else None
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


def normalize_designation(raw: str) -> str:
    """
    Convert designation:
      - lowercase
      - remove spaces
      - remove '-', '/', '(', ')'
    """
    if raw is None:
        return ""
    s = raw.lower()
    s = "".join(s.split())
    for ch in ["-", "/", "(", ")"]:
        s = s.replace(ch, "")
    return s


def _cleanup_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _parse_int(s: str) -> Optional[int]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    s = s.replace(",", "")
    if not re.fullmatch(r"\d+", s):
        return None
    return int(s)


def _attempt_ocr_page(page: Any) -> str:
    # pdfplumber's to_image uses PIL; OCR the rendered page at a moderate resolution.
    image: Image.Image = page.to_image(resolution=int(os.getenv("OCR_RESOLUTION", "300"))).original
    return pytesseract.image_to_string(image)


def _dedupe_products(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        nd = r.get("normalized_designation") or ""
        if not nd:
            continue
        existing = deduped.get(nd)
        if not existing:
            deduped[nd] = r
            continue
        # Prefer richer rows (automotive rows carry pack/case).
        score_existing = int(existing.get("pack_code") is not None) + int(
            existing.get("case_qty") is not None
        )
        score_new = int(r.get("pack_code") is not None) + int(
            r.get("case_qty") is not None
        )
        if score_new > score_existing:
            deduped[nd] = r
            continue
        if score_new == score_existing and int(r.get("price", 0)) > int(
            existing.get("price", 0)
        ):
            deduped[nd] = r
    return list(deduped.values())


def parse_automotive_text(
    text: str, source_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Automotive format (6 columns):
      sl_no | designation | contents | pack_code | case_qty | MRP
    """
    if not text:
        return []

    price_min = int(os.getenv("PRICE_MIN", "100"))
    price_max = int(os.getenv("PRICE_MAX", "100000"))

    lines = [_cleanup_ws(ln) for ln in text.splitlines() if _cleanup_ws(ln)]
    out: List[Dict[str, Any]] = []

    # A row usually starts with sl-no + designation, or directly a designation.
    row_start_re = re.compile(
        r"^(?:\d+\s+)?(?:[A-Za-z]{2,12}\s*\d[\dA-Za-z/\-()]*|\d{4,}[\dA-Za-z/\-()]*)\b"
    )
    acc = ""
    for line in lines:
        lower = line.lower()
        if any(
            tok in lower
            for tok in [
                "sl no",
                "designation",
                "contents",
                "pack code",
                "case qty",
                "mrp",
            ]
        ):
            continue
        if row_start_re.match(line):
            if acc:
                parsed = _parse_automotive_row(
                    acc, source_file=source_file, price_min=price_min, price_max=price_max
                )
                if parsed:
                    out.append(parsed)
            acc = line
        elif acc:
            acc = f"{acc} {line}"

    if acc:
        parsed = _parse_automotive_row(
            acc, source_file=source_file, price_min=price_min, price_max=price_max
        )
        if parsed:
            out.append(parsed)

    return _dedupe_products(out)


def _parse_automotive_row(
    row_text: str,
    source_file: Optional[str],
    price_min: int,
    price_max: int,
) -> Optional[Dict[str, Any]]:
    row_text = _cleanup_ws(row_text)
    if not row_text:
        return None

    # designation near start, optional leading serial number.
    m = re.search(
        r"^(?:\d+\s+)?(?P<designation>(?:[A-Za-z]{2,12}\s*\d[\dA-Za-z/\-()]*|\d{4,}[\dA-Za-z/\-()]*))(?:\s|$)",
        row_text,
    )
    if not m:
        return None
    designation = _cleanup_ws(m.group("designation"))
    if not re.search(r"\d{3,}", designation):
        return None

    int_tokens = re.findall(r"\d[\d,]*", row_text)
    if len(int_tokens) < 3:
        return None
    pack_raw, case_raw, price_raw = int_tokens[-3], int_tokens[-2], int_tokens[-1]
    try:
        pack_code = pack_raw.replace(",", "")
        case_qty = int(case_raw.replace(",", ""))
        price = int(price_raw.replace(",", ""))
    except Exception:
        return None

    # Swap if OCR/line-wrap confuses case_qty vs MRP.
    if price < price_min and case_qty >= price_min:
        price, case_qty = case_qty, price

    if case_qty < 1 or case_qty > 500:
        return None
    if price < price_min or price > price_max:
        return None

    contents: Optional[str] = None
    try:
        designation_end = m.end("designation")
        pack_idx = row_text.rfind(pack_raw)
        if pack_idx > designation_end:
            c = _cleanup_ws(row_text[designation_end:pack_idx])
            if c:
                contents = c
    except Exception:
        contents = None

    return {
        "designation": designation,
        "normalized_designation": normalize_designation(designation),
        "contents": contents,
        "pack_code": pack_code or None,
        "case_qty": case_qty,
        "price": price,
        "source_file": source_file,
        "last_updated": datetime.now(timezone.utc),
    }


def parse_industrial_text(
    text: str, source_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Industrial format (no headings):
      designation | price | designation | price
    """
    if not text:
        return []
    pmin = int(os.getenv("FORMAT2_PRICE_MIN", os.getenv("PRICE_MIN", "100")))
    pmax = int(os.getenv("FORMAT2_PRICE_MAX", os.getenv("PRICE_MAX", "100000")))
    # Industrial PDFs often wrap cells so that a designation can appear on one
    # extracted line and the corresponding price on the next line. The strict
    # "designation price" regex would miss those pairs unless we merge such
    # wrapped fragments.
    raw_lines = [_cleanup_ws(ln) for ln in text.splitlines() if _cleanup_ws(ln)]
    lines: List[str] = []
    acc: str | None = None
    acc_has_num = False
    for ln in raw_lines:
        has_num = bool(re.search(r"\d", ln))
        if acc is None:
            if not has_num:
                acc = ln
                acc_has_num = False
            else:
                lines.append(ln)
            continue

        # If accumulated text had no numbers and this line has numbers, merge.
        if not acc_has_num and has_num:
            lines.append(f"{acc} {ln}")
            acc = None
            acc_has_num = False
            continue

        # Keep extending non-numeric fragments.
        if not has_num:
            acc = f"{acc} {ln}"
            acc_has_num = False
            continue

        # acc already contained numbers (or mixed), flush it and start anew.
        lines.append(acc)
        acc = ln
        acc_has_num = has_num

    if acc:
        lines.append(acc)
    out: List[Dict[str, Any]] = []

    def push_pair(designation_raw: Optional[str], price_raw: Optional[str]) -> None:
        if not designation_raw or not price_raw:
            return
        designation = _cleanup_ws(designation_raw)
        price = _parse_int(price_raw)
        if not price:
            return
        if price < pmin or price > pmax:
            return
        # industrial part numbers should contain a digit run
        # (some OCR extractions may break longer digit runs, so require >=2).
        if not re.search(r"\d{2,}", designation):
            return
        out.append(
            {
                "designation": designation,
                "normalized_designation": normalize_designation(designation),
                "contents": None,
                "pack_code": None,
                "case_qty": None,
                "price": price,
                "source_file": source_file,
                "last_updated": datetime.now(timezone.utc),
            }
        )

    # Primary matcher: expected 2-pair line.
    dual_re = re.compile(
        r"^(?P<d1>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)]+?)\s+(?P<p1>\d[\d,]*)\s+"
        r"(?P<d2>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)]+?)\s+(?P<p2>\d[\d,]*)$"
    )
    # Salvage left or right pair independently when one side is malformed.
    left_re = re.compile(
        r"^(?P<d>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)]{1,90}?)\s+(?P<p>\d[\d,]*)\b"
    )
    right_re = re.compile(
        r"(?P<d>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)]{1,90}?)\s+(?P<p>\d[\d,]*)$"
    )

    # Extra fallback: extract any number of "designation price" pairs from a line.
    # This is useful when the PDF text extraction adds extra spaces/columns so the
    # strict full-row regex doesn't match, but individual pairs still do.
    pair_re = re.compile(
        r"(?P<d>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)\.]{1,80}?[A-Za-z0-9])\s+(?P<p>\d[\d,]*)"
    )

    for line in lines:
        m = dual_re.match(line)
        if m:
            # Validate/store each side independently (critical improvement).
            push_pair(m.group("d1"), m.group("p1"))
            push_pair(m.group("d2"), m.group("p2"))
            continue

        # Fallback salvage path: keep whichever side parses.
        ml = left_re.search(line)
        mr = right_re.search(line)
        if ml:
            push_pair(ml.group("d"), ml.group("p"))
        if mr:
            # avoid double-pushing exact same pair from both regexes
            if not (ml and ml.group("d") == mr.group("d") and ml.group("p") == mr.group("p")):
                push_pair(mr.group("d"), mr.group("p"))

        # Final fallback: pair extraction anywhere in the line.
        # Use a per-line set to avoid duplicates from overlapping matches.
        found: set[tuple[str, int]] = set()
        for pm in pair_re.finditer(line):
            d_raw = pm.group("d")
            p_raw = pm.group("p")
            d_clean = _cleanup_ws(d_raw)
            p_val = _parse_int(p_raw)
            if not d_clean or not p_val:
                continue
            nd = normalize_designation(d_clean)
            if not nd:
                continue
            key = (nd, p_val)
            if key in found:
                continue
            found.add(key)
            push_pair(d_clean, p_raw)

    return _dedupe_products(out)


def parse_pdf_to_products(
    pdf_path: str,
    source_file: Optional[str],
    price_list_type: Literal["automotive", "industrial"],
) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    ocr_enabled = os.getenv("OCR_ENABLED", "true").lower() in ("1", "true", "yes")
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = (page.extract_text(x_tolerance=1, y_tolerance=1) or "").strip()
            parsed: List[Dict[str, Any]] = []
            if text:
                parsed = (
                    parse_automotive_text(text, source_file)
                    if price_list_type == "automotive"
                    else parse_industrial_text(text, source_file)
                )
            if ocr_enabled and not parsed:
                try:
                    ocr_text = (_attempt_ocr_page(page) or "").strip()
                    parsed = (
                        parse_automotive_text(ocr_text, source_file)
                        if price_list_type == "automotive"
                        else parse_industrial_text(ocr_text, source_file)
                    )
                except Exception:
                    logger.exception("OCR failed for page %s", idx + 1)
            products.extend(parsed)
    return _dedupe_products(products)


class SearchResult(BaseModel):
    designation: str
    normalized_designation: str
    price: int
    pack_code: Optional[str] = None
    case_qty: Optional[int] = None
    source_type: Literal["automotive", "industrial"]
    score: float


def normalize_query(q: str) -> str:
    if q is None:
        return ""
    s = q.lower()
    # Remove words like "bearing", "bearings", "price"
    s = regex_lib.sub(r"\b(bearings?|price)\b", " ", s, flags=regex_lib.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return normalize_designation(s)


def _search_in_table(
    db: Session,
    table_name: str,
    source_type: Literal["automotive", "industrial"],
    norm: str,
    prefix: str,
    min_similarity: float,
    limit: int,
) -> List[Dict[str, Any]]:
    sql = text(
        f"""
        SELECT
            :source_type AS source_type,
            designation,
            normalized_designation,
            price,
            pack_code,
            case_qty,
            (
                CASE
                    WHEN normalized_designation = :norm THEN 1000
                    WHEN normalized_designation LIKE :prefix THEN 500
                    ELSE 0
                END
                + similarity(normalized_designation, :norm) * 100
            ) AS score
        FROM {table_name}
        WHERE
            normalized_designation = :norm
            OR normalized_designation LIKE :prefix
            OR similarity(normalized_designation, :norm) > :min_sim
        ORDER BY score DESC
        LIMIT :lim
        """
    )
    return (
        db.execute(
            sql,
            {
                "source_type": source_type,
                "norm": norm,
                "prefix": prefix,
                "min_sim": min_similarity,
                "lim": max(1, min(int(limit), 50)),
            },
        )
        .mappings()
        .all()
    )


def search_products(
    db: Session, q: str, limit: int = 10, min_similarity: float = 0.15
) -> List[SearchResult]:
    norm = normalize_query(q)
    if not norm:
        return []

    prefix = f"{norm}%"
    lim = max(1, min(int(limit), 50))

    automotive_rows = _search_in_table(
        db,
        table_name="automotive_products",
        source_type="automotive",
        norm=norm,
        prefix=prefix,
        min_similarity=min_similarity,
        limit=lim,
    )
    industrial_rows = _search_in_table(
        db,
        table_name="industrial_products",
        source_type="industrial",
        norm=norm,
        prefix=prefix,
        min_similarity=min_similarity,
        limit=lim,
    )

    # Keep both sources visible; do not dedupe across tables.
    combined = [dict(r) for r in automotive_rows] + [dict(r) for r in industrial_rows]
    combined.sort(key=lambda x: float(x["score"]), reverse=True)
    # Return a larger merged window so one source does not hide the other.
    merged_limit = min(lim * 2, 100)
    return [SearchResult(**row) for row in combined[:merged_limit]]


app = FastAPI(title="Voice Searchable Price List System (backend)")

# CORS: `allow_origins=["*"]` with `allow_credentials=True` is invalid — browsers block the
# response (axios shows ERR_NETWORK). Use explicit origins + credentials, or wildcard + no credentials.
_cors_origins_raw = (os.getenv("CORS_ORIGINS", "*").strip() or "*")
if _cors_origins_raw == "*":
    _cors_origins: List[str] = ["*"]
    _cors_credentials = False
else:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    _cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db() -> None:
    if not engine:
        return
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS automotive_products_normalized_designation_trgm_idx
                ON automotive_products USING GIN (normalized_designation gin_trgm_ops);
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS industrial_products_normalized_designation_trgm_idx
                ON industrial_products USING GIN (normalized_designation gin_trgm_ops);
                """
            )
        )


@app.on_event("startup")
def _startup() -> None:
    try:
        init_db()
    except Exception:
        logger.exception("DB init failed")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    source_file: Optional[str] = Form(None),
    price_list_type: Literal["automotive", "industrial"] = Form(...),
) -> Dict[str, Any]:
    if not engine or not SessionLocal:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are supported.")

    source_name = source_file or file.filename

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file upload.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        parsed_products = parse_pdf_to_products(
            tmp_path,
            source_file=source_name,
            price_list_type=price_list_type,
        )
        if not parsed_products:
            return {"parsed": 0, "upserted": 0, "unique_normalized": 0}

        target_model = (
            AutomotiveProduct
            if price_list_type == "automotive"
            else IndustrialProduct
        )

        with SessionLocal() as db:
            # CRITICAL: upsert should modify ALL details.
            payload_rows = [
                {
                    "designation": p["designation"],
                    "normalized_designation": p["normalized_designation"],
                    "contents": p.get("contents"),
                    "pack_code": p.get("pack_code"),
                    "case_qty": p.get("case_qty"),
                    "price": p["price"],
                    "source_file": p.get("source_file"),
                    "last_updated": p["last_updated"],
                }
                for p in parsed_products
                if p.get("normalized_designation")
            ]

            stmt = pg_insert(target_model).values(payload_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["normalized_designation"],
                set_={
                    "designation": stmt.excluded.designation,
                    # Preserve existing non-null details when the newly parsed row has NULLs
                    # (common with Format 2 and OCR fallback).
                    "contents": func.coalesce(
                        stmt.excluded.contents, target_model.contents
                    ),
                    "pack_code": func.coalesce(
                        stmt.excluded.pack_code, target_model.pack_code
                    ),
                    "case_qty": func.coalesce(
                        stmt.excluded.case_qty, target_model.case_qty
                    ),
                    "price": stmt.excluded.price,
                    "source_file": func.coalesce(
                        stmt.excluded.source_file, target_model.source_file
                    ),
                    "last_updated": stmt.excluded.last_updated,
                },
            )
            db.execute(stmt)
            db.commit()

        unique_norms = len({p["normalized_designation"] for p in payload_rows})

        upload_debug = os.getenv("UPLOAD_DEBUG", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        resp: Dict[str, Any] = {
            "parsed": len(parsed_products),
            "upserted": len(payload_rows),
            "unique_normalized": unique_norms,
        }
        if upload_debug:
            resp["sample"] = [
                {
                    "designation": r["designation"],
                    "normalized_designation": r["normalized_designation"],
                    "price": r["price"],
                    "pack_code": r.get("pack_code"),
                    "case_qty": r.get("case_qty"),
                }
                for r in payload_rows[:12]
            ]

        return resp
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@app.get("/search", response_model=List[SearchResult])
def search_endpoint(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    min_similarity: float = Query(0.15, ge=0.0, le=1.0),
) -> List[SearchResult]:
    if not engine or not SessionLocal:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured.")

    with SessionLocal() as db:
        return search_products(db, q=q, limit=limit, min_similarity=min_similarity)

