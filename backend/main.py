import os
import re
import uuid
import logging
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pdfplumber
import pytesseract
import regex as regex_lib
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from sqlalchemy import DateTime, Integer, String, Text, create_engine, text, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("price-search")


DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    logger.warning("DATABASE_URL is not set. Backend endpoints will fail until configured.")

# Ensure pytesseract can find the tesseract binary even when PATH isn't updated.
_tesseract_cmd_env = os.getenv("TESSERACT_CMD")
_tesseract_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if _tesseract_cmd_env:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd_env
elif os.path.exists(_tesseract_default):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_default


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    designation: Mapped[str] = mapped_column(String, nullable=False)
    # CRITICAL: normalized_designation must be unique.
    normalized_designation: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    contents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pack_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    case_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    price: Mapped[int] = mapped_column(Integer, nullable=False)

    source_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
) if DATABASE_URL else None

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


def parse_format2(text: str, source_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Format 2 (dual column): each visual row contains TWO products.
    Expect extracted lines like:
      "3308 A/C3 14021    3317 A/C3 76444"
    Create TWO DB records with designation+price only.
    """
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []

    # Heuristic: one line should contain two designation blocks plus two numeric prices.
    dual_re = re.compile(
        r"^(?P<d1>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)]+?)\s+(?P<p1>\d[\d,]*)\s+"
        r"(?P<d2>[A-Za-z0-9][A-Za-z0-9\s\-\(/\)]+?)\s+(?P<p2>\d[\d,]*)$"
    )

    for line in lines:
        # Skip obvious non-data lines.
        if any(tok.lower() in line.lower() for tok in ["note", "product designation", "rsp", "inr", "skf"]):
            continue

        m = dual_re.match(line)
        if not m:
            continue

        d1 = _cleanup_ws(m.group("d1"))
        d2 = _cleanup_ws(m.group("d2"))
        p1 = _parse_int(m.group("p1"))
        p2 = _parse_int(m.group("p2"))
        if not p1 or not p2:
            continue
        if not re.search(r"\d", d1) or not re.search(r"\d", d2):
            continue

        now = datetime.now(timezone.utc)
        out.append(
            {
                "designation": d1,
                "normalized_designation": normalize_designation(d1),
                "contents": None,
                "pack_code": None,
                "case_qty": None,
                "price": p1,
                "source_file": source_file,
                "last_updated": now,
            }
        )
        out.append(
            {
                "designation": d2,
                "normalized_designation": normalize_designation(d2),
                "contents": None,
                "pack_code": None,
                "case_qty": None,
                "price": p2,
                "source_file": source_file,
                "last_updated": now,
            }
        )

    # Drop empty normalized values.
    return [r for r in out if r.get("normalized_designation")]


def parse_format1(text: str, source_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Format 1 (table): designation | contents | pack_code | case_qty | price
    rows may span multiple lines

    OCR note:
    Real PDFs often include a leading row number column (e.g. "44 VKTC 0955 ...").
    For robustness, we:
      - allow optional leading digits before the designation
      - parse `pack_code`, `case_qty`, `price` from the last three integer tokens
    """
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []

    # Avoid treating format-2 designations (e.g. "3308 A/C3") as format-1 by requiring a letter-prefix plus digits.
    designation_start_re = re.compile(r"^(?:\d+\s+)?[A-Za-z]{2,12}\s*\d")

    def integer_token_count(s: str) -> int:
        return len(re.findall(r"\d[\d,]*", s))

    acc = ""
    for line in lines:
        lower = line.lower()
        if any(tok in lower for tok in ["note", "skf", "r s p", "rsp", "mrp"]):
            # Skip obvious non-row fragments.
            continue

        if designation_start_re.match(line):
            # If previous accumulator already has enough numeric tokens, flush it.
            if acc and integer_token_count(acc) >= 3:
                out.extend(_parse_format1_row(acc, source_file=source_file))
                acc = ""
            # Start new row.
            acc = line
            continue

        if acc:
            acc = f"{acc} {line}"
            if integer_token_count(acc) >= 3:
                out.extend(_parse_format1_row(acc, source_file=source_file))
                acc = ""

    if acc:
        out.extend(_parse_format1_row(acc, source_file=source_file))

    return [r for r in out if r.get("normalized_designation")]


def _parse_format1_row(row_text: str, source_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse a single accumulated row into:
      designation, contents, pack_code, case_qty, price

    OCR-tolerant approach:
    - designation: first letter+digits token (allow optional leading row number)
    - pack_code/case_qty/price: last three integer tokens in the row
    """
    row_text = _cleanup_ws(row_text)
    if not row_text:
        return []

    # Extract integers in order, then take the last 3 as (pack_code, case_qty, price).
    int_tokens = re.findall(r"\d[\d,]*", row_text)
    if len(int_tokens) < 3:
        return []
    pack_token_raw = int_tokens[-3]
    try:
        pack_code_i = pack_token_raw.replace(",", "")
        case_qty_i = int_tokens[-2].replace(",", "")
        price_i = int_tokens[-1].replace(",", "")
        pack_code = str(pack_code_i)
        case_qty = int(case_qty_i)
        price = int(price_i)
    except Exception:
        return []

    # Basic plausibility filters (especially important for OCR fallback).
    # Typical SKF price tables have prices in the hundreds+ and case quantities as small integers.
    if price < 100:
        return []
    if case_qty < 1 or case_qty > 200:
        return []

    # Extract designation near the start.
    m = re.search(
        r"^(?:\d+\s+)?(?P<designation>[A-Za-z]{2,12}\s*\d[\dA-Za-z/\-()]*)(?:\s|$)",
        row_text,
    )
    if not m:
        # Fallback: search anywhere for a letter prefix followed by digits.
        m = re.search(r"(?P<designation>[A-Za-z]{2,12}\s*\d[\dA-Za-z/\-()]{0,12})", row_text)
    if not m:
        return []

    designation = _cleanup_ws(m.group("designation"))
    contents: Optional[str] = None

    # Best-effort contents extraction: text between designation and pack_code token.
    # This works well for real text extraction; OCR may still produce noisy values.
    try:
        designation_end = m.end("designation")
        pack_idx = row_text.rfind(pack_token_raw)
        if pack_idx != -1 and pack_idx > designation_end:
            c = row_text[designation_end:pack_idx].strip()
            if c:
                contents = _cleanup_ws(c)
    except Exception:
        contents = None

    # Another plausibility filter: part numbers typically contain multiple digits (>= 3 in a row).
    if not re.search(r"\d{3,}", designation):
        return []

    now = datetime.now(timezone.utc)
    return [
        {
            "designation": designation,
            "normalized_designation": normalize_designation(designation),
            "contents": contents or None,
            "pack_code": pack_code or None,
            "case_qty": case_qty,
            "price": price,
            "source_file": source_file,
            "last_updated": now,
        }
    ]


def parse_pdf_to_products(pdf_path: str, source_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Pipeline:
      Step 1: Extract raw text using pdfplumber
      Step 2: Split into lines
      Step 3: Detect format
      OCR fallback if needed
    """
    products: List[Dict[str, Any]] = []
    ocr_enabled = os.getenv("OCR_ENABLED", "true").lower() in ("1", "true", "yes")

    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=1, y_tolerance=1) or ""
            text = text.strip()

            f1: List[Dict[str, Any]] = []
            f2: List[Dict[str, Any]] = []

            if text:
                f1 = parse_format1(text, source_file=source_file)
                f2 = parse_format2(text, source_file=source_file)

            # If we got nothing (or almost nothing), try OCR for that page.
            if ocr_enabled and (not f1 and not f2):
                try:
                    ocr_text = _attempt_ocr_page(page)
                    ocr_text = (ocr_text or "").strip()
                    f1 = parse_format1(ocr_text, source_file=source_file)
                    f2 = parse_format2(ocr_text, source_file=source_file)
                except Exception:
                    logger.exception("OCR failed for page %s", idx + 1)

            # Format detection logic: if one format clearly dominates, take it.
            if len(f2) >= len(f1) + 3 and len(f2) > 0:
                products.extend(f2)
            elif len(f1) > 0 and len(f1) >= len(f2):
                products.extend(f1)
            else:
                products.extend(f1)
                products.extend(f2)

    # Dedupe within the upload by normalized_designation (last wins).
    deduped: Dict[str, Dict[str, Any]] = {}
    for p in products:
        nd = p.get("normalized_designation") or ""
        if not nd:
            continue
        deduped[nd] = p
    return list(deduped.values())


class SearchResult(BaseModel):
    designation: str
    normalized_designation: str
    price: int
    pack_code: Optional[str] = None
    case_qty: Optional[int] = None
    score: float


def normalize_query(q: str) -> str:
    if q is None:
        return ""
    s = q.lower()
    # Remove words like "bearing", "bearings", "price"
    s = regex_lib.sub(r"\b(bearings?|price)\b", " ", s, flags=regex_lib.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return normalize_designation(s)


def search_products(db: Session, q: str, limit: int = 10, min_similarity: float = 0.15) -> List[SearchResult]:
    norm = normalize_query(q)
    if not norm:
        return []

    prefix = f"{norm}%"
    # Prefer exact match, then prefix match, then fuzzy via pg_trgm similarity.
    sql = text(
        """
        SELECT
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
        FROM products
        WHERE
            normalized_designation = :norm
            OR normalized_designation LIKE :prefix
            OR similarity(normalized_designation, :norm) > :min_sim
        ORDER BY score DESC
        LIMIT :lim
        """
    )
    rows = db.execute(
        sql,
        {
            "norm": norm,
            "prefix": prefix,
            "min_sim": min_similarity,
            "lim": max(1, min(int(limit), 50)),
        },
    ).mappings().all()

    return [SearchResult(**row) for row in rows]


app = FastAPI(title="Voice Searchable Price List System (backend)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
                CREATE INDEX IF NOT EXISTS products_normalized_designation_trgm_idx
                ON products USING GIN (normalized_designation gin_trgm_ops);
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
        parsed_products = parse_pdf_to_products(tmp_path, source_file=source_name)
        if not parsed_products:
            return {"parsed": 0, "upserted": 0, "unique_normalized": 0}

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

            stmt = pg_insert(Product).values(payload_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["normalized_designation"],
                set_={
                    "designation": stmt.excluded.designation,
                    # Preserve existing non-null details when the newly parsed row has NULLs
                    # (common with Format 2 and OCR fallback).
                    "contents": func.coalesce(stmt.excluded.contents, Product.contents),
                    "pack_code": func.coalesce(stmt.excluded.pack_code, Product.pack_code),
                    "case_qty": func.coalesce(stmt.excluded.case_qty, Product.case_qty),
                    "price": stmt.excluded.price,
                    "source_file": func.coalesce(stmt.excluded.source_file, Product.source_file),
                    "last_updated": stmt.excluded.last_updated,
                },
            )
            db.execute(stmt)
            db.commit()

        unique_norms = len({p["normalized_designation"] for p in parsed_products})
        return {"parsed": len(parsed_products), "upserted": len(parsed_products), "unique_normalized": unique_norms}
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

