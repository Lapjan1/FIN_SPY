"""
FastAPI API - DB-first: Extract -> persist to .db -> all products read from DB.
Per AGENTS.md commands: uv run fastapi dev apps/api/main.py --port 8000
Auth, dual DB, Paystack and trial-page flows follow prior-art research (see docs/AUTH_PAYSTACK.md) with FIN_SPY upgrades:

Pattern notes:
- Dual SQLite/Postgres via db.py is_postgres() + _translate
- require_login/require_subscription as FastAPI Depends + bcrypt
- Paystack initialize/verify/webhook with timing-safe signature compare
- POPIA privacy templates route

DB-first: Every write goes to .db before next step, audit_log hash-chain SHA256(prev||canonical_json) per AGENTS.md
"""
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr
from decimal import Decimal
from typing import List, Optional
import hashlib
import os
import json
import threading
from pathlib import Path

from .db import init_db, get_db, append_audit_log, get_setting, env_or_setting, compute_row_hash, get_last_audit_hash
from .auth import (
    require_login, require_subscription, require_admin, require_owner_or_admin,
    create_user, verify_user, create_reset_token, verify_reset_token, use_reset_token,
    get_user, get_trial_pages_remaining, check_session_secret, get_current_user_id, hash_password, is_admin_user
)
from .paystack import (
    has_paystack, get_paystack_pk, get_paystack_sk, initialize_transaction, verify_transaction,
    handle_webhook_event, verify_paystack_signature, plan_details, get_paystack_plans
)

app = FastAPI(
    title="FIN_SPY API",
    version="0.1.0",
    description="Financial Surveillance & Peak Insights - DB-first forensic books + spy + KPIs + debt strategies. Built with Meta Muse."
)

def _cors_origins() -> list:
    """Browser origins allowed to call the API: localhost dev defaults plus
    WEB_ORIGIN env (comma-separated, one per deployed web service)."""
    origins = ["http://127.0.0.1:3000", "http://localhost:3000"]
    for origin in os.getenv("WEB_ORIGIN", "").split(","):
        origin = origin.strip().rstrip("/")
        if origin and origin not in origins:
            origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _worker_enabled() -> bool:
    return os.getenv("WORKER_ENABLED", "false").lower() in ("1", "true", "yes")


def _maybe_start_worker() -> bool:
    """Start the extraction poll loop in-process when enabled.

    Railway: API + vault share one disk, so a separate worker service could not
    read uploads - the loop runs here as a daemon thread (single uvicorn worker).
    Local dev keeps python -m apps.worker.main with WORKER_ENABLED unset (default off).
    """
    if not _worker_enabled():
        return False
    from apps.worker.main import worker_loop
    threading.Thread(target=worker_loop, kwargs={'poll_interval': 5}, name='finspy-worker', daemon=True).start()
    return True


# Init DB on startup (tables + Paystack columns)
@app.on_event("startup")
def startup():
    init_db()
    _maybe_start_worker()
    # Check session secret fail-closed in production
    try:
        check_session_secret()
    except RuntimeError as e:
        # In dev allow, in prod fail
        if os.getenv("ENVIRONMENT") == "production":
            raise
        print(f"WARN: {e} - dev mode allowed")

# --- Pydantic models (Decimal not float per AGENTS.md) ---
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = ""
    tenant_id: str = "default-tenant"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TransactionOut(BaseModel):
    id: str
    tenant_id: str
    txn_date: str
    description_raw: str
    amount_minor: int
    direction: str
    balance_after_minor: Optional[int] = None
    fingerprint_sha256: str
    status: str
    doc_id: str
    page_no: int
    line_ids: List[str]
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    original_filename: Optional[str] = None
    nature: Optional[str] = None
    category_id: Optional[str] = None

class DashboardSummary(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    account_number: Optional[str] = None
    active_template: str = "personal"
    totals: Optional[dict] = None
    leak_score_per_month_minor: int
    runway_months: float
    burn_rate_minor: int
    savings_rate_pct: float
    private_vs_business_ratio: float
    inflow_minor: int = 0
    outflow_minor: int = 0
    net_flow_minor: int = 0
    is_inflow_understood: bool = True
    is_outflow_understood: bool = True
    trial_pages_remaining: Optional[int] = None

class BooksSelectIn(BaseModel):
    template: str = Field(..., description="One of personal|sme_cc|mixed_sole_prop")

def _validate_period(from_date: Optional[str], to_date: Optional[str]):
    import re
    pat = r"^\d{4}-\d{2}-\d{2}$"
    if from_date and not re.match(pat, from_date):
        raise HTTPException(422, f"Invalid parameters: from_date must be YYYY-MM-DD, got '{from_date}'")
    if to_date and not re.match(pat, to_date):
        raise HTTPException(422, f"Invalid parameters: to_date must be YYYY-MM-DD, got '{to_date}'")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, f"Invalid parameters: from_date '{from_date}' must be <= to_date '{to_date}'")

class DebtInput(BaseModel):
    creditor: str
    balance_minor: int
    apr_pct: Decimal = Field(..., description="Annual APR as decimal e.g. 21 for 21%")
    min_payment_minor: int

class DebtPlanRequest(BaseModel):
    debts: List[DebtInput]
    method: str = Field(..., pattern="^(snowball|avalanche)$")
    extra_cash_per_month_minor: int = 0

class ImageGenIn(BaseModel):
    prompt: str
    size: str = "1024x1024"
    model: str | None = None

class SegmentIn(BaseModel):
    image_b64: str
    points: list | None = None
    boxes: list | None = None

class ChatRequest(BaseModel):
    messages: List[dict]
    tenant_id: str = "default-tenant"

class ForgotIn(BaseModel):
    email: EmailStr

class ResetIn(BaseModel):
    token: str
    password: str = Field(..., min_length=6)

# --- Helpers ---
VAULT_PATH = Path(os.getenv("VAULT_PATH", "./data/vault"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fingerprint_txn(date: str, amount_minor: int, desc_norm: str) -> str:
    canonical = f"{date}|{amount_minor}|{desc_norm.lower().strip()}"
    return hashlib.sha256(canonical.encode()).hexdigest()

# --- Auth Routes ---
@app.post("/v1/auth/register")
def register(inp: RegisterIn):
    uid = create_user(inp.email, inp.password, inp.name, inp.tenant_id)
    try:
        from .email import send_welcome_email
        send_welcome_email(inp.email, inp.name, tenant_id=inp.tenant_id)
    except Exception:
        pass  # email must never break registration
    return {"id": uid, "email": inp.email, "tenant_id": inp.tenant_id, "message": "Registered - use X-User-Id header for dev auth"}

@app.post("/v1/auth/login")
def login(inp: LoginIn):
    uid = verify_user(inp.email, inp.password)
    if not uid:
        raise HTTPException(401, "Invalid credentials")
    user = get_user(uid)
    return {"id": uid, "email": inp.email, "tenant_id": user.get("tenant_id") if user else "default-tenant", "message": "Use X-User-Id header with this id for dev auth, Bearer token for prod"}

@app.post("/v1/auth/forgot")
def forgot(inp: ForgotIn):
    token = create_reset_token(inp.email)
    if token:
        from .email import get_email_api_key, send_reset_email
        try:
            db = get_db()
            ucur = db.execute("SELECT tenant_id FROM users WHERE email=?", (inp.email.lower(),))
            urow = ucur.fetchone()
            utenant = (urow["tenant_id"] if isinstance(urow, dict) else urow[0]) if urow else "default-tenant"
            send_reset_email(inp.email, token, tenant_id=utenant)
        except Exception:
            pass
        if get_email_api_key():
            return {"sent": True}  # prod: token emailed, never returned
        return {"sent": True, "reset_token": token, "note": "Dev mode (no email key): token returned for testing."}
    # Always return sent=true to avoid user enumeration
    return {"sent": True}

@app.post("/v1/auth/reset")
def reset(inp: ResetIn):
    ok = use_reset_token(inp.token, inp.password)
    if not ok:
        raise HTTPException(400, "Invalid or expired token")
    return {"ok": True}

@app.get("/v1/auth/me")
def me(user_id: int = Depends(require_login)):
    user = get_user(user_id)
    trial = get_trial_pages_remaining(user_id)
    return {"user": user, "trial_pages_remaining": trial, "is_trial_unlimited": trial is None}

@app.get("/v1/me/export")
def export_my_data(user_id: int = Depends(require_login)):
    """POPIA subject-access export: everything held on your tenant."""
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from .reports import build_popia_zip
    zip_path = build_popia_zip(tenant_id)
    append_audit_log(tenant_id, user_id, "account.data_export", "users",
                     str(user_id), {"file": Path(zip_path).name})
    return FileResponse(zip_path, media_type="application/zip",
                        filename=f"finspy-my-data-{_safe_name(tenant_id, 'export')}.zip")


# --- Health with env guard ---
@app.get("/health")
def health():
    db = get_db()
    # Check REQUIRED envs fail-closed
    required = []
    if os.getenv("ENVIRONMENT") == "production":
        if not os.getenv("SESSION_SECRET"):
            required.append("SESSION_SECRET missing - fail-closed")
    return {"status": "ok", "version": "0.1.0", "db_first": True, "backend": db.backend, "has_paystack": has_paystack(), "required_checks": required}

@app.get("/health/ready")
def ready():
    # /health/ready checks DB + essential env
    try:
        db = get_db()
        db.execute("SELECT 1")
        return {"ready": True, "backend": db.backend}
    except Exception as e:
        raise HTTPException(500, f"Not ready: {e}")

# --- Documents with auth + trial + audit hash-chain + encrypted PDF handling ---
@app.post("/v1/documents")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    pdf_password: Optional[str] = Form(None),
    user_id: int = Depends(require_subscription)
):
    """
    Intake vault: hash SHA256, store content-addressed immutable, audit log hash-chain, enqueue job.
    Requires subscription + trial pages check.
    Handles encrypted/password protected PDFs: detect is_encrypted, try password param (from Form or X-PDF-Password header), never log/store password, audit encrypted status.
    Per AGENTS.md lethal trifecta: private data + untrusted PDF + egress never same session - password handled transiently.
    """
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large >50MB")
    if not file.filename.lower().endswith(('.pdf','.csv','.ofx','.jpg','.jpeg','.png')):
        raise HTTPException(400, "Unsupported type")
    if file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        # No OCR stage exists yet (extractor raises) - fail fast with
        # 422 instead of spending trial quota on a doomed document.
        raise HTTPException(
            422,
            "Invalid parameters: image uploads need OCR, which is not"
            " wired yet - please upload a PDF, CSV or OFX statement.",
        )

    db = get_db()
    tenant_id = _tenant_of(user_id)

    # Trial pages check
    remaining = get_trial_pages_remaining(user_id)
    if remaining is not None and remaining <= 0:
        raise HTTPException(402, "Trial uploads exhausted - subscribe")

    sha = sha256_bytes(data)
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    storage_key = VAULT_PATH / f"{sha}.pdf"

    # Detect encrypted PDF - never log password per AGENTS.md
    is_encrypted = False
    encryption_method = None
    pdf_needs_password = False
    if file.filename.lower().endswith('.pdf'):
        try:
            import fitz
            # Try open without password to detect encryption
            doc = fitz.open(stream=data, filetype="pdf")
            if doc.is_encrypted:
                is_encrypted = True
                encryption_method = "PDF standard encryption"
                # Check if needs password
                if doc.needs_pass:
                    pdf_needs_password = True
            doc.close()
        except Exception:
            # If fitz fails, try pdfplumber detection? For now mark as unknown, allow upload
            pass

    # Try to open with provided password if encrypted
    password_provided = pdf_password or request.headers.get("X-PDF-Password")
    # PDF password NEVER in the request body - resolved from an OS env var
    if not password_provided:
        password_provided = request.headers.get("X-PDF-Password-Env")
        if password_provided:
            # Resolve from env var name, not value directly
            env_var_name = password_provided
            password_provided = os.getenv(env_var_name)

    status = "queued"
    if is_encrypted and pdf_needs_password:
        if not password_provided:
            status = "needs_password"
        else:
            # Try to authenticate with provided password
            try:
                import fitz
                doc = fitz.open(stream=data, filetype="pdf")
                # Try auth
                auth_result = doc.authenticate(password_provided)
                if auth_result == 0:
                    # Failed auth
                    status = "needs_password"
                else:
                    status = "queued"
                doc.close()
            except Exception:
                status = "needs_password"

    # Vault is a global content store (bytes once); documents are per-tenant rows.
    bytes_restored = False
    if not storage_key.exists():
        storage_key.write_bytes(data)
        bytes_restored = True
    doc_id = hashlib.sha256(f"{tenant_id}|{sha}".encode()).hexdigest()[:16]
    cur = db.execute("SELECT id, status FROM source_documents WHERE tenant_id=? AND sha256=?", (tenant_id, sha))
    existing = cur.fetchone()
    if existing:
        ex_id = existing["id"] if isinstance(existing, dict) else existing[0]
        ex_status = existing["status"] if isinstance(existing, dict) else existing[1]
        requeued = False
        if bytes_restored and ex_status != "queued":
            # Disk was wiped (redeploy) while the DB row survived: bytes
            # are back now, so requeue for extraction instead of
            # stranding the user on "already in your vault".
            db.execute("UPDATE source_documents SET status='queued' WHERE id=?", (ex_id,))
            append_audit_log(tenant_id, user_id, "document.restore_requeue",
                             "source_documents", ex_id,
                             {"sha256": sha, "from_status": ex_status})
            db.commit()
            ex_status = "queued"
            requeued = True
        return {
            "id": ex_id,
            "sha256": sha,
            "storage_key": str(storage_key),
            "original_filename": file.filename,
            "size_bytes": len(data),
            "status": ex_status,
            "duplicate": True,
            "requeued": requeued,
            "bytes_restored": bytes_restored,
            "is_encrypted": is_encrypted,
            "needs_password": pdf_needs_password,
            "tenant_id": tenant_id,
            "trial_pages_remaining": get_trial_pages_remaining(user_id)
        }
    # Append source_documents + audit_log hash-chain
    try:
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, mime, storage_key, original_filename, uploaded_by, upload_ip, user_agent, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, tenant_id, sha, len(data), file.content_type or "application/pdf", str(storage_key), file.filename, user_id, request.client.host if request.client else "", request.headers.get("user-agent",""), status)
        )
        # Audit log append with prev_hash/row_hash per AGENTS.md - never log password
        audit_payload = {"sha256": sha, "filename": file.filename, "size": len(data), "is_encrypted": is_encrypted, "needs_password": pdf_needs_password, "encryption_method": encryption_method}
        append_audit_log(tenant_id, user_id, "document.upload", "source_documents", doc_id, audit_payload)
        db.commit()
    except Exception as e:
        print(f"Document already exists or error: {e}")

    return {
        "id": doc_id,
        "sha256": sha,
        "storage_key": str(storage_key),
        "original_filename": file.filename,
        "size_bytes": len(data),
        "status": status,
        "duplicate": False,
        "is_encrypted": is_encrypted,
        "needs_password": pdf_needs_password,
        "tenant_id": tenant_id,
        "trial_pages_remaining": get_trial_pages_remaining(user_id)
    }

@app.get("/v1/documents")
def list_documents(request: Request, user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    cur = db.execute("SELECT id, sha256, original_filename, size_bytes, status, uploaded_at_utc, account_id, account_number, bank_name, branch_code FROM source_documents WHERE tenant_id=? ORDER BY uploaded_at_utc DESC LIMIT 100", (tenant_id,))
    rows = cur.fetchall()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]

@app.get("/v1/transactions")
def list_transactions(request: Request, status: Optional[str] = None, account_number: Optional[str] = None, document_id: Optional[str] = None, user_id: int = Depends(require_login)) -> List[TransactionOut]:
    db = get_db()
    tenant_id = _tenant_of(user_id)
    unknown_only = account_number == "__unknown"
    if account_number and not unknown_only:
        brow = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND account_number=?", (tenant_id, account_number)).fetchone()
        if not brow:
            raise HTTPException(422, f"Invalid parameters: unknown account_number '{account_number}' for tenant")
    # Read from DB, not extraction directly - DB-first per AGENTS.md
    q = "SELECT t.*, d.original_filename, d.bank_name, c.nature, c.category_id FROM transactions t LEFT JOIN source_documents d ON t.document_id=d.id AND d.tenant_id=t.tenant_id LEFT JOIN classifications c ON c.transaction_id=t.id AND c.tenant_id=t.tenant_id AND NOT EXISTS (SELECT 1 FROM classifications c2 WHERE c2.transaction_id=t.id AND c2.tenant_id=t.tenant_id AND c2.decided_at_utc > c.decided_at_utc) WHERE t.tenant_id=?"
    params: list = [tenant_id]
    if status:
        q += " AND t.status=?"
        params.append(status)
    if unknown_only:
        q += " AND (t.account_number IS NULL OR t.account_number='')"
    elif account_number:
        q += " AND t.account_number=?"
        params.append(account_number)
    if document_id:
        q += " AND t.document_id=?"
        params.append(document_id)
    q += " ORDER BY t.txn_date DESC LIMIT 100"
    cur = db.execute(q, tuple(params))
    # For scaffold, return empty if none, else map
    rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        out.append(TransactionOut(
            id=d.get("id",""), tenant_id=d.get("tenant_id",tenant_id), txn_date=d.get("txn_date","2026-10-26"),
            description_raw=d.get("description_raw",""), amount_minor=d.get("amount_minor",0),
            direction=d.get("direction","debit"), balance_after_minor=d.get("balance_after_minor"),
            fingerprint_sha256=d.get("fingerprint_sha256",""), status=d.get("status","proposed"),
            doc_id=d.get("document_id",""), page_no=1, line_ids=[],
            account_number=d.get("account_number"), bank_name=d.get("bank_name"),
            original_filename=d.get("original_filename"), nature=d.get("nature"),
            category_id=d.get("category_id"),
        ))
    return out

@app.get("/v1/transactions/{txn_id}/sources")
def get_sources(txn_id: str, user_id: int = Depends(require_login)):
    db = get_db()
    # Isolation check: ensure txn belongs to user's tenant
    cur = db.execute("SELECT tenant_id, document_id FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Transaction not found")
    t_tenant = row["tenant_id"] if isinstance(row, dict) else row[0]
    if t_tenant != _tenant_of(user_id):
        raise HTTPException(403, detail="Cross-tenant access denied - isolation guard")
    doc_id = row["document_id"] if isinstance(row, dict) else (row[1] if len(row) > 1 else None)
    doc_sha, doc_name = None, None
    if doc_id:
        dcur = db.execute("SELECT sha256, original_filename FROM source_documents WHERE id=?", (doc_id,))
        drow = dcur.fetchone()
        if drow:
            doc_sha = drow["sha256"] if isinstance(drow, dict) else drow[0]
            doc_name = drow["original_filename"] if isinstance(drow, dict) else (drow[1] if len(drow) > 1 else None)
    # Returns page_no + bbox + page dims for highlight overlay - signature demo
    cur = db.execute("SELECT ss.page_no, ss.line_id, ss.bbox_x0, ss.bbox_y0, ss.bbox_x1, ss.bbox_y1, ss.page_width, ss.page_height FROM transaction_sources ts JOIN source_spans ss ON ts.span_id=ss.id WHERE ts.transaction_id=?", (txn_id,))
    spans = cur.fetchall()
    if not spans:
        return {"txn_id": txn_id, "document_id": doc_id, "doc_sha256": doc_sha,
                "original_filename": doc_name, "page_no": 1,
                "page_width": None, "page_height": None, "line_ids": [],
                "bboxes": [], "unlinked": True}
    bboxes = [{"line_id": (s["line_id"] if isinstance(s, dict) else s[1]),
               "x0": (s["bbox_x0"] if isinstance(s, dict) else s[2]),
               "y0": (s["bbox_y0"] if isinstance(s, dict) else s[3]),
               "x1": (s["bbox_x1"] if isinstance(s, dict) else s[4]),
               "y1": (s["bbox_y1"] if isinstance(s, dict) else s[5])} for s in spans]
    first = spans[0]
    page_no = first["page_no"] if isinstance(first, dict) else first[0]
    width = first["page_width"] if isinstance(first, dict) else (first[6] if len(first) > 6 else None)
    height = first["page_height"] if isinstance(first, dict) else (first[7] if len(first) > 7 else None)
    return {"txn_id": txn_id, "document_id": doc_id, "doc_sha256": doc_sha,
            "original_filename": doc_name, "page_no": page_no,
            "page_width": width, "page_height": height,
            "line_ids": [b["line_id"] for b in bboxes], "bboxes": bboxes}

@app.get("/v1/documents/{doc_id}/file")
def get_document_file(doc_id: str, user_id: int = Depends(require_login)):
    """Serve the vault PDF bytes for the drill viewer. Tenant-guarded."""
    db = get_db()
    cur = db.execute("SELECT tenant_id, sha256, storage_key, original_filename FROM source_documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    t_tenant = row["tenant_id"] if isinstance(row, dict) else row[0]
    if t_tenant != _tenant_of(user_id):
        raise HTTPException(403, detail="Cross-tenant access denied - isolation guard")
    sha = row["sha256"] if isinstance(row, dict) else row[1]
    stored = row["storage_key"] if isinstance(row, dict) else (row[2] if len(row) > 2 else None)
    fname = row["original_filename"] if isinstance(row, dict) else (row[3] if len(row) > 3 else "document.pdf")
    path = Path(stored) if stored else VAULT_PATH / f"{sha}.pdf"
    if not path.exists():
        path = VAULT_PATH / f"{sha}.pdf"
    if not path.exists():
        raise HTTPException(404, "Vault file missing for document")
    return FileResponse(str(path), media_type="application/pdf", filename=fname or "document.pdf")

@app.post("/v1/documents/{doc_id}/requeue")
def requeue_document(doc_id: str, user_id: int = Depends(require_login)):
    """Retry a failed document: exception -> queued for the worker.

    Re-uploading identical bytes returns duplicate:true without reprocessing,
    so this is the only path to re-run a failed extraction (e.g. after the
    extraction model was fixed). Owner-only, consumes no trial, audit-logged.
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)
    cur = db.execute("SELECT * FROM source_documents WHERE id=?", (doc_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    doc = dict(row) if not isinstance(row, dict) else row
    if doc.get("tenant_id") != tenant_id:
        raise HTTPException(403, "Cross-tenant access denied - isolation guard")
    status = doc.get("status")
    if status == "queued":
        return {"id": doc_id, "status": "queued", "requeued": False}
    if status != "exception":
        raise HTTPException(
            422,
            "Invalid parameters: only failed (exception) documents can be"
            f" requeued, got '{status}'",
        )
    db.execute("UPDATE source_documents SET status='queued' WHERE id=?", (doc_id,))
    append_audit_log(
        tenant_id,
        user_id,
        "document.requeue",
        "source_documents",
        doc_id,
        {"from": status, "to": "queued"},
    )
    db.commit()
    return {"id": doc_id, "status": "queued", "requeued": True}


@app.get("/v1/books/templates")
def list_book_templates(user_id: int = Depends(require_login)):
    from apps.worker.parsers.registry import get_coa_templates
    tmpls = get_coa_templates()
    return {"templates": [{"name": k, "description": v.get("description",""), "count": len(v.get("accounts",[]))} for k,v in tmpls.items()]}

@app.get("/v1/books/active")
def get_active_book(user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from apps.worker.parsers.registry import get_active_template
    active = get_active_template(tenant_id)
    cur = db.execute("SELECT COUNT(*) as cnt FROM accounts WHERE tenant_id=?", (tenant_id,))
    r = cur.fetchone()
    total = r["cnt"] if isinstance(r, dict) else r[0]
    return {"tenant_id": tenant_id, "active_template": active, "total_accounts": total}

@app.get("/v1/accounts")
def list_accounts(user_id: int = Depends(require_login)):
    """Active-books chart of accounts (code + name) for the review selector.

    Seeded on first use so a fresh tenant always has a valid list. Bank
    ledger rows (per account_number) are excluded - this is the category
    list acceptance may post to, in the same order the books use.
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from apps.worker.parsers.registry import ensure_coa_seeded

    active = ensure_coa_seeded(tenant_id, db=db)
    cur = db.execute(
        "SELECT id, code, name, type, account_number FROM accounts"
        " WHERE tenant_id=? AND template=? ORDER BY code ASC",
        (tenant_id, active),
    )
    rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    seed_prefix = f"acc-{tenant_id}-{active}-"
    rows.sort(
        key=lambda d: (
            d.get("code") or "",
            0 if str(d.get("id") or "").startswith(seed_prefix) else 1,
            0 if not d.get("account_number") else 1,
        )
    )
    seen = set()
    accounts = []
    for d in rows:
        if d.get("account_number") or d.get("code") in seen:
            continue
        seen.add(d.get("code"))
        accounts.append(
            {
                "id": d.get("id"),
                "code": d.get("code"),
                "name": d.get("name"),
                "type": d.get("type"),
            }
        )
    return {
        "tenant_id": tenant_id,
        "active_template": active,
        "accounts": accounts,
    }


def _require_account(tenant_id: str, account_number) -> None:
    """422 when an account filter names a bank account the tenant lacks."""
    if not account_number or account_number == "__unknown":
        return
    cur = get_db().execute(
        "SELECT id FROM accounts WHERE tenant_id=? AND account_number=?",
        (tenant_id, account_number))
    if not cur.fetchone():
        raise HTTPException(
            422, f"Invalid parameters: account_number '{account_number}'"
            " does not exist for tenant. Use GET /v1/bank-accounts.")


@app.post("/v1/books/select")
def select_book(inp: BooksSelectIn, user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from apps.worker.parsers.registry import set_active_template, VALID_TEMPLATES
    if inp.template not in VALID_TEMPLATES:
        raise HTTPException(422, f"Invalid parameters: template must be one of {VALID_TEMPLATES}, got '{inp.template}'")
    try:
        set_active_template(tenant_id, inp.template)
    except ValueError as e:
        raise HTTPException(422, str(e))
    append_audit_log(tenant_id, user_id, "books.select", "tenants", tenant_id, {"active_template": inp.template})
    db.commit()
    return {"tenant_id": tenant_id, "active_template": inp.template, "message": f"Now working with '{inp.template}' books only. Other templates remain seeded but inactive."}

@app.get("/v1/dashboard/summary")
def dashboard_summary(request: Request, from_date: Optional[str] = None, to_date: Optional[str] = None, account_number: Optional[str] = None, user_id: int = Depends(require_login)):
    _validate_period(from_date, to_date)
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from apps.worker.parsers.registry import get_active_template
    active = get_active_template(tenant_id)
    # Validate account_number exists for tenant if provided (never work on non-existing accounts)
    if account_number and account_number != "__unknown":
        cur = db.execute("SELECT id FROM accounts WHERE tenant_id=? AND account_number=?", (tenant_id, account_number))
        if not cur.fetchone():
            raise HTTPException(422, f"Invalid parameters: account_number '{account_number}' does not exist for tenant. Seed COA and use an existing account.")
    # Load transactions for period (totals first)
    q = "SELECT id, txn_date, description_raw, amount_minor, direction, account_number FROM transactions WHERE tenant_id=?"
    params: list = [tenant_id]
    if from_date:
        q += " AND txn_date>=?"
        params.append(from_date)
    if to_date:
        q += " AND txn_date<=?"
        params.append(to_date)
    if account_number == "__unknown":
        q += " AND (account_number IS NULL OR account_number='')"
    elif account_number:
        q += " AND account_number=?"
        params.append(account_number)
    q += " ORDER BY txn_date ASC LIMIT 5000"
    cur = db.execute(q, tuple(params))
    txns = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    # If no data, return zero totals (not mock) so percentages derive from totals
    from apps.worker.spy.kpi import compute_kpis
    # Current balance: sum of signed in period or last balance_after? Use net as proxy
    kpis = compute_kpis(txns, current_balance_minor=None, from_date=from_date, to_date=to_date, account_number=None if account_number == "__unknown" else account_number)
    trial = get_trial_pages_remaining(user_id)
    # Leak score: use subscription creep or outflow avg
    leak = kpis.get("subscription_creep_minor", 0) or 0
    return {
        "from_date": from_date,
        "to_date": to_date,
        "account_number": account_number,
        "active_template": active,
        "totals": kpis.get("totals"),
        "leak_score_per_month_minor": leak,
        "runway_months": kpis.get("runway_months", 0),
        "burn_rate_minor": kpis.get("burn_rate_minor", 0),
        "savings_rate_pct": kpis.get("savings_rate_pct", 0),
        "private_vs_business_ratio": kpis.get("private_vs_business_ratio", 0),
        "inflow_minor": kpis.get("inflow_minor", 0),
        "outflow_minor": kpis.get("outflow_minor", 0),
        "net_flow_minor": kpis.get("net_flow_minor", 0),
        "is_inflow_understood": True,
        "is_outflow_understood": True,
        "trial_pages_remaining": trial,
        "is_trial_unlimited": trial is None
    }

@app.get("/v1/bank-accounts")
def bank_accounts(user_id: int = Depends(require_login)):
    """Distinct bank accounts with txn counts for the global picker."""
    db = get_db()
    tenant_id = _tenant_of(user_id)
    cur = db.execute(
        "SELECT a.account_number, MAX(d.bank_name) AS bank_name, COUNT(t.id) AS txn_count, MAX(d.uploaded_at_utc) AS last_upload"
        " FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id AND t.tenant_id=a.tenant_id"
        " LEFT JOIN source_documents d ON d.account_number=a.account_number AND d.tenant_id=a.tenant_id"
        " WHERE a.tenant_id=? AND a.account_number IS NOT NULL AND a.account_number NOT IN ('', 'unknown')"
        " GROUP BY a.account_number ORDER BY bank_name, a.account_number",
        (tenant_id,))
    out = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    # Unknown scope: rows the extractor could not attribute. Counted from
    # transactions (the filter source of truth), not the placeholder row.
    urow = db.execute(
        "SELECT COUNT(*) AS n FROM transactions WHERE tenant_id=?"
        " AND (account_number IS NULL OR account_number='')",
        (tenant_id,)).fetchone()
    n = urow["n"] if isinstance(urow, dict) else urow[0]
    if n:
        out.append({"account_number": None, "bank_name": None,
                    "txn_count": n, "last_upload": None})
    return out

@app.get("/v1/review-queue")
def review_queue(user_id: int = Depends(require_login)):
    """
    Review queue per docs/PLAN.md: failed checks land in review queue; user confirms or edits (each edit = revision with reason)
    Returns transactions with status proposed|exception|needs_password that failed reconciliation gate or low confidence
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)
    # Get transactions that need review: status proposed with warnings, exception, needs_password, or from extraction_runs with reconciliation fail
    cur = db.execute("""
        SELECT t.id, t.txn_date, t.description_raw, t.amount_minor, t.direction, t.status, t.fingerprint_sha256,
               t.account_number, d.original_filename, d.sha256 as doc_sha256, er.reconciliation, er.status as run_status
        FROM transactions t
        JOIN source_documents d ON t.document_id = d.id
        LEFT JOIN extraction_runs er ON t.run_id = er.id
        WHERE t.tenant_id=? AND t.status IN ('proposed','exception','needs_password')
        ORDER BY t.txn_date DESC LIMIT 100
    """, (tenant_id,))
    rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        result.append(d)
    # Also get documents that need password or exception
    cur = db.execute("""
        SELECT id, original_filename, sha256, status, is_encrypted, upload_ip, uploaded_at_utc
        FROM source_documents WHERE tenant_id=? AND status IN ('needs_password','exception','queued')
        ORDER BY uploaded_at_utc DESC LIMIT 50
    """, (tenant_id,)) if False else db.execute("SELECT id, original_filename, sha256, status, uploaded_at_utc FROM source_documents WHERE tenant_id=? AND status IN ('needs_password','exception','queued') ORDER BY uploaded_at_utc DESC LIMIT 50", (tenant_id,))
    # The above second query uses simpler schema existing - status column exists
    docs = cur.fetchall()
    return {"transactions": result, "documents": [dict(r) if not isinstance(r, dict) else r for r in docs], "count": len(result)}

@app.get("/v1/flags")
def flags(user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    cur = db.execute("SELECT * FROM flags WHERE tenant_id=? ORDER BY created_at DESC LIMIT 50", (tenant_id,))
    rows = cur.fetchall()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]

@app.post("/v1/debt/plan")
def debt_plan(req: DebtPlanRequest, user_id: int = Depends(require_login)):
    from apps.worker.spy.debt import Debt, plan_debts, what_if_extra
    try:
        debts = [Debt(creditor=d.creditor, balance_minor=d.balance_minor,
                      apr_pct=d.apr_pct, min_payment_minor=d.min_payment_minor)
                 for d in req.debts]
        plan = plan_debts(debts, req.extra_cash_per_month_minor, req.method)
    except ValueError as e:
        raise HTTPException(422, str(e))
    out = dict(plan)
    if req.extra_cash_per_month_minor > 0:
        out["what_if"] = what_if_extra(debts, req.extra_cash_per_month_minor, req.method)
    return out

@app.get("/v1/debt/defaults")
def debt_defaults(user_id: int = Depends(require_login)):
    """Extra-cash default from the tenant's own ledger: average monthly net
    (inflow minus outflow) across months with postings. Clamped at zero -
    a negative average never prefills negative cash."""
    db = get_db()
    tenant_id = _tenant_of(user_id)
    cur = db.execute(
        "SELECT substr(txn_date, 1, 7) AS month,"
        " SUM(CASE WHEN direction='credit' THEN amount_minor"
        " WHEN direction='debit' THEN -ABS(amount_minor) ELSE 0 END) AS net"
        " FROM transactions WHERE tenant_id=? AND status != 'rejected'"
        " GROUP BY month",
        (tenant_id,))
    nets = [int(r["net"] if isinstance(r, dict) else r[1]) for r in cur.fetchall()]
    months = len(nets)
    avg = int(round(sum(nets) / months)) if months else 0
    return {"tenant_id": tenant_id,
            "months": months,
            "avg_net_per_month_minor": avg,
            "extra_cash_default_minor": max(avg, 0)}

@app.post("/v1/spy/run")
def spy_run(user_id: int = Depends(require_login)):
    """Run Day-5 spy detectors over tenant transactions, persist flags.

    Deterministic flag ids: re-runs overwrite, never duplicate.
    """
    import json
    from apps.worker.spy import detectors as det
    db = get_db()
    tenant_id = _tenant_of(user_id)
    cur = db.execute(
        "SELECT id, txn_date, description_raw, amount_minor, direction,"
        " fingerprint_sha256 FROM transactions WHERE tenant_id=? ORDER BY txn_date ASC",
        (tenant_id,))
    txns = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    if not txns:
        return {"tenant_id": tenant_id, "txn_count": 0, "flags": 0, "by_code": {}}
    found = (det.detect_recurring(txns) + det.detect_duplicate(txns)
             + det.detect_fee(txns) + det.detect_anomaly_iqr(txns)
             + det.detect_benford(txns))
    leak = det.leak_score_per_month(txns)
    if leak > 0:
        found.append({"type": "subscription_leak", "code": "F-020",
                      "leak_per_month_minor": leak})
    window_start = min(t.get("txn_date", "") for t in txns)
    window_end = max(t.get("txn_date", "") for t in txns)
    severity = {"DUP": "high", "NDUP": "high", "F-030": "medium", "F-010": "info",
                "SUB": "info", "F-020": "info", "BEN": "low", "RP": "medium"}
    by_code: dict = {}
    for f in found:
        code = f.get("code", "UNK")
        key = f.get("tx_id") or f.get("merchant") or f.get("type")
        fid = det.flag_id(tenant_id, code, str(key))
        db.execute(
            "INSERT OR REPLACE INTO flags (id, tenant_id, test_id, params_json,"
            " severity, window_start, window_end, result_json, code_version)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (fid, tenant_id, code, json.dumps({"type": f.get("type")}),
             severity.get(code, "info"), window_start, window_end,
             json.dumps(f), "day5-v1"))
        by_code[code] = by_code.get(code, 0) + 1
    db.commit()
    append_audit_log(tenant_id, user_id, "spy.run", "flags", tenant_id,
                     {"txn_count": len(txns), "flags": len(found), "by_code": by_code})
    db.commit()
    return {"tenant_id": tenant_id, "txn_count": len(txns), "flags": len(found),
            "by_code": by_code, "leak_per_month_minor": leak}

@app.post("/v1/chat")
def chat(req: ChatRequest, user_id: int = Depends(require_login)):
    tenant_id = _tenant_of(user_id)
    if req.tenant_id != tenant_id:
        raise HTTPException(403, detail="Cross-tenant access denied - isolation guard")
    msgs = req.messages or []
    question = ""
    for m in reversed(msgs):
        if isinstance(m, dict) and m.get("role") == "user" and m.get("content"):
            question = str(m["content"])
            break
    if not question:
        raise HTTPException(422, "Invalid parameters: messages must include a user message")
    from apps.worker.spy.chat import chat_answer
    return chat_answer(tenant_id, question)

@app.post("/v1/reports")
def create_report(kind: str = "excel", account_number: Optional[str] = None, request: Request = None, user_id: int = Depends(require_subscription)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    report_id = hashlib.sha256(f"{tenant_id}{kind}{os.urandom(8)}".encode()).hexdigest()[:16]
    db.execute("INSERT INTO reports (id, tenant_id, kind, generated_by) VALUES (?,?,?,?)", (report_id, tenant_id, kind, user_id))
    append_audit_log(tenant_id, user_id, f"report.create.{kind}", "reports", report_id, {"kind": kind})
    db.commit()

    # P0-J (D8): no queue - every known kind generates synchronously.
    # Unknown kinds 422 instead of vanishing into a fake 'queued' state.
    known = ("powerbi", "excel", "auditor-csv", "evidence-pack", "signed-pdf")
    if kind not in known:
        raise HTTPException(
            422,
            f"Invalid parameters: unknown report kind '{kind}'. "
            f"Expected one of {', '.join(known)}",
        )
    try:
        if kind == "powerbi":
            from .reports import generate_powerbi_pack
            _require_account(tenant_id, account_number)
            pack = generate_powerbi_pack(tenant_id, account_number)
            db.execute("UPDATE reports SET file_key=?, file_sha256=?, manifest_key=? WHERE id=?", (pack["file_key"], pack["sha256"], pack["csv_dir"], report_id))
            db.commit()
            return {"id": report_id, "kind": kind, "status": "ready", "file_key": pack["file_key"], "sha256": pack["sha256"], "counts": pack["counts"], "csv_dir": pack["csv_dir"]}
        if kind == "excel":
            from .reports import generate_excel_workbook
            _require_account(tenant_id, account_number)
            wb = generate_excel_workbook(tenant_id, None, None,
                                        account_number)
            db.execute("UPDATE reports SET file_key=?, file_sha256=? WHERE id=?", (wb["file_key"], wb["sha256"], report_id))
            db.commit()
            return {"id": report_id, "kind": kind, "status": "ready", "file_key": wb["file_key"], "sha256": wb["sha256"]}
        if kind == "auditor-csv":
            from .reports import generate_auditor_csv
            _require_account(tenant_id, account_number)
            csv_pack = generate_auditor_csv(tenant_id, account_number)
            db.execute("UPDATE reports SET file_key=?, file_sha256=? WHERE id=?", (csv_pack["file_key"], csv_pack["sha256"], report_id))
            db.commit()
            return {"id": report_id, "kind": kind, "status": "ready", "file_key": csv_pack["file_key"], "sha256": csv_pack["sha256"], "count": csv_pack["count"]}
        if kind == "evidence-pack":
            from .reports import generate_evidence_pack
            pack = generate_evidence_pack(tenant_id)
            db.execute("UPDATE reports SET file_key=?, file_sha256=? WHERE id=?", (pack["file_key"], pack["sha256"], report_id))
            db.commit()
            return {"id": report_id, "kind": kind, "status": "ready", "file_key": pack["file_key"], "sha256": pack["sha256"], "file_count": pack["file_count"]}
        from .signing import build_and_sign
        out = build_and_sign(tenant_id, None, None)
        db.execute("UPDATE reports SET file_key=?, file_sha256=? WHERE id=?", (out["file_key"], out["sha256"], report_id))
        db.commit()
        return {"id": report_id, "kind": kind, "status": "ready", "file_key": out["file_key"], "sha256": out["sha256"]}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        return {"id": report_id, "kind": kind, "status": "failed", "error": str(e)}

@app.get("/v1/reports/powerbi")
def get_powerbi_pack(account_number: Optional[str] = None,
                       user_id: int = Depends(require_login)):
    """
    PowerBI-ready pack: Excel file with star-schema sheets + CSVs per homework Part 5.10
    fact_transactions, fact_journal, dim_date, dim_account, dim_category, dim_entity, dim_document as Excel + CSVs + guide
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)

    from .reports import generate_powerbi_pack, bundle_powerbi_zip
    _require_account(tenant_id, account_number)
    pack = generate_powerbi_pack(tenant_id, account_number)

    # Audit log
    append_audit_log(tenant_id, user_id, "report.powerbi", "reports", pack["file_key"], {"counts": pack["counts"]})

    return FileResponse(bundle_powerbi_zip(pack), media_type="application/zip",
                        filename=f"finspy-powerbi-{_safe_name(tenant_id, 'export')}.zip")

@app.post("/v1/images/generate")
def images_generate(req: ImageGenIn, user_id: int = Depends(require_login)):
    """Explicit text-to-image (Wonder). 422 unless an image provider is configured."""
    from apps.worker.llm.image import generate_image
    try:
        return generate_image(req.prompt, size=req.size, model=req.model)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Image provider failed: {e}")

@app.post("/v1/images/segment")
def images_segment(req: SegmentIn, user_id: int = Depends(require_login)):
    """SAM segmentation via configured self-hosted service. 422 unless configured."""
    from apps.worker.llm.image import segment_image
    try:
        return segment_image(req.image_b64, points=req.points, boxes=req.boxes)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"SAM service failed: {e}")

@app.get("/v1/reports/evidence-pack")
def get_evidence_pack(sign: bool = False, user_id: int = Depends(require_login)):
    """
    Evidence Pack ZIP per Appendix C/D: originals + reports + audit chain +
    manifest.json + manifest.sha256. Verify with scripts/verify_pack.py.
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)

    from .reports import generate_evidence_pack
    pack = generate_evidence_pack(tenant_id, sign=sign)
    append_audit_log(tenant_id, user_id, "report.evidence_pack", "reports",
                     pack["report_id"],
                     {"sha256": pack["sha256"], "file_count": pack["file_count"],
                      "signed": pack.get("signed", False)})
    _warn = (pack.get("sign_warning") or "")[:200]
    return FileResponse(pack["file_key"], media_type="application/zip",
                        filename=f"finspy-evidence-{_safe_name(pack['report_id'], 'pack')}.zip",
                        headers={"X-Report-Warning": _warn} if _warn else None)

@app.get("/v1/reports/signed-pdf")
def get_signed_pdf(from_date: str = None, to_date: str = None, user_id: int = Depends(require_login)):
    """
    PAdES-signed summary PDF: built from DB, signed with configured cert,
    RFC3161-timestamped when a TSA is reachable (else explicit warning).
    422 when signing is not configured or the window exceeds 12 months.
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)

    from .signing import build_and_sign
    try:
        out = build_and_sign(tenant_id, from_date, to_date)
    except ValueError as e:
        raise HTTPException(422, str(e))
    append_audit_log(tenant_id, user_id, "report.signed_pdf", "reports",
                     out["file_key"], {"sha256": out["sha256"],
                                       "timestamped": out["signed"]["timestamped"]})
    _warn = (out["signed"]["warning"] or "")[:200]
    return FileResponse(out["file_key"], media_type="application/pdf",
                        filename=f"finspy-summary-{_safe_name(from_date, 'all')}-to-{_safe_name(to_date, 'all')}.pdf",
                        headers={"X-Report-Warning": _warn} if _warn else None)

@app.get("/v1/reports/excel")
def get_excel_workbook(from_date: str = None, to_date: str = None,
                         account_number: Optional[str] = None,
                         user_id: int = Depends(require_login)):
    """
    Excel workbook per Appendix G + P&L + Balance Sheet (12 sheets, 12-month max window).
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)

    from .reports import generate_excel_workbook
    try:
        _require_account(tenant_id, account_number)
        wb = generate_excel_workbook(tenant_id, from_date, to_date,
                                    account_number)
    except ValueError as e:
        raise HTTPException(422, str(e))
    append_audit_log(tenant_id, user_id, "report.excel", "reports", wb["file_key"], {"sha256": wb["sha256"]})
    return FileResponse(wb["file_key"],
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        filename=f"finspy-workbook-{_safe_name(from_date, 'all')}-to-{_safe_name(to_date, 'all')}.xlsx")

@app.get("/v1/reports/auditor-csv")
def get_auditor_csv(vendor: Optional[str] = None, account_number: Optional[str] = None, user_id: int = Depends(require_login)):
    """
    CSV for auditor to input in their bookkeeping package per user decision:
    Export package the auditor can use the data export to csv and input in their bookkeeping package
    For our usage we document transactions and we can view and represent the data in any way to enhance personal or sme businesse
    Per docs/DISCLAIMER.md: private/business only, mixed exceptional startup, respect and give info and user deals with auditor and SARS
    Query params: vendor normalized merchant filter to export just a vendor if we do own set of books so user can export vendor and add all transactions to certain account if like, sort and add rule
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)

    from .reports import generate_auditor_csv

    # If vendor filter, generate custom CSV filtered by vendor + account_number
    if vendor:
        # Call with filter - for MVP, we filter inside generate_auditor_csv? For now, pass vendor via custom query
        # For simplicity, generate full pack then filter in endpoint? We'll implement filtered version
        # Here we call generate_auditor_csv then filter? Actually generate_auditor_csv queries all, but we can add filtering logic
        # For competition, we support vendor filter via direct query
        cur = db.execute("SELECT t.id, t.txn_date as date, t.description_raw as description, t.amount_minor, t.currency, t.direction, t.balance_after_minor, t.fingerprint_sha256, t.status, t.account_number, t.document_id, c.nature, c.business_pct, c.category_id, c.rationale, c.confidence, c.source, c.decided_by, a.code as account_code, a.name as account_name, a.type as account_type, a.bank_name, a.branch_code, d.original_filename, d.sha256 as doc_sha256 FROM transactions t LEFT JOIN classifications c ON t.id=c.transaction_id LEFT JOIN accounts a ON t.account_id=a.id LEFT JOIN source_documents d ON t.document_id=d.id WHERE t.tenant_id=? AND LOWER(t.description_raw) LIKE ?" + (" AND t.account_number=?" if account_number else "") + " ORDER BY t.txn_date ASC",
                       (tenant_id, f"%{vendor.lower()}%", account_number) if account_number else (tenant_id, f"%{vendor.lower()}%"))
        rows = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
        # Write filtered CSV
        from pathlib import Path
        import csv, hashlib
        from datetime import datetime, timezone
        from apps.api.reports import REPORTS_PATH
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_vendor = _safe_name(vendor, "vendor")
        csv_path = REPORTS_PATH / f"auditor_export_vendor_{safe_vendor}_{tenant_id}_{timestamp}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            fieldnames = ["id","date","description","amount_minor","amount_rands","currency","direction","balance_after_minor","fingerprint","status","account_number","bank_name","branch_code","account_code","account_name","account_type","nature","business_pct","category_id","rationale","confidence","source","decided_by","document_id","original_filename","doc_sha256"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({
                    "id": r.get('id',''),"date": r.get('date',''),"description": r.get('description',''),"amount_minor": r.get('amount_minor',''),"amount_rands": f"{r.get('amount_minor',0)/100:.2f}" if r.get('amount_minor') else "","currency": r.get('currency','ZAR'),"direction": r.get('direction',''),"balance_after_minor": r.get('balance_after_minor',''),"fingerprint": r.get('fingerprint_sha256',''),"status": r.get('status',''),"account_number": r.get('account_number',''),"bank_name": r.get('bank_name',''),"branch_code": r.get('branch_code',''),"account_code": r.get('account_code',''),"account_name": r.get('account_name',''),"account_type": r.get('account_type',''),"nature": r.get('nature',''),"business_pct": r.get('business_pct',''),"category_id": r.get('category_id',''),"rationale": r.get('rationale',''),"confidence": r.get('confidence',''),"source": r.get('source',''),"decided_by": r.get('decided_by',''),"document_id": r.get('document_id',''),"original_filename": r.get('original_filename',''),"doc_sha256": r.get('doc_sha256',''),
                })
        sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest() if csv_path.exists() else ""
        append_audit_log(tenant_id, user_id, "report.auditor_csv.vendor", "reports", str(csv_path), {"vendor": vendor, "account_number": account_number, "count": len(rows), "sha256": sha256})
        return FileResponse(str(csv_path), media_type="text/csv",
                            filename=f"finspy-auditor-{safe_vendor}.csv")

    _require_account(tenant_id, account_number)
    csv_pack = generate_auditor_csv(tenant_id, account_number)
    append_audit_log(tenant_id, user_id, "report.auditor_csv", "reports", csv_pack["file_key"], {"count": csv_pack["count"], "sha256": csv_pack["sha256"]})
    return FileResponse(csv_pack["file_key"], media_type="text/csv",
                        filename="finspy-auditor.csv")

@app.get("/v1/reports/{report_id}")
def get_report(report_id: str, user_id: int = Depends(require_login)):
    db = get_db()
    cur = db.execute("SELECT * FROM reports WHERE id=?", (report_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    r = dict(row) if not isinstance(row, dict) else row
    # Isolation check
    u_tenant = _tenant_of(user_id)
    if r.get("tenant_id") != u_tenant:
        raise HTTPException(403, "Cross-tenant denied")
    return r

# --- Billing Routes ---
@app.get("/v1/billing/plans")
def billing_plans():
    return {
        "free": {"name": "Free", "pages": 20, "amount_minor": 0, "price_display": "R0"},
        "individual": {"name": "Individual", "pages": 200, "amount_minor": 14900, "price_display": "R149/mo"},
        "sme": {"name": "SME", "pages": 1000, "amount_minor": 59900, "price_display": "R599/mo"},
    }

@app.post("/v1/billing/checkout")
def billing_checkout(plan_code: str = "individual", user_id: int = Depends(require_login), request: Request = None):
    db = get_db()
    cur = db.execute("SELECT email, tenant_id FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    email = row["email"] if isinstance(row, dict) else row[0]
    tenant_id = row["tenant_id"] if isinstance(row, dict) else row[1]
    # Build absolute callback URL (proxy-aware)
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    # user_id query lets require_login accept the browser redirect (dev auth; prod needs JWT per AUTH_PAYSTACK)
    callback_url = f"{base_url}/v1/billing/callback?user_id={user_id}"
    try:
        data = initialize_transaction(email, plan_code, callback_url, user_id, tenant_id)
        if data.get("free"):
            return {"checkout_url": None, "plan_code": plan_code, "free": True}
        return {"checkout_url": data.get("authorization_url"), "access_code": data.get("access_code"), "reference": data.get("reference"), "plan_code": plan_code}
    except Exception as e:
        raise HTTPException(500, f"Paystack init failed: {e}")

@app.get("/v1/billing/callback")
def paystack_callback(trxref: str = "", reference: str = "", user_id: int = Depends(require_login)):
    # Paystack callback: verify + activate subscription
    ref = trxref or reference
    if not ref:
        raise HTTPException(400, "Missing reference")
    try:
        data = verify_transaction(ref)
        # Update user subscription fields
        customer_code = data.get("customer", {}).get("customer_code", "") if isinstance(data.get("customer"), dict) else data.get("customer", "")
        auth_code = data.get("authorization", {}).get("authorization_code", "") if isinstance(data.get("authorization"), dict) else ""
        db = get_db()
        db.execute("UPDATE users SET paystack_customer_code=?, paystack_authorization_code=?, subscription_status='active' WHERE id=?", (customer_code, auth_code, user_id))
        db.commit()
        return {"ok": True, "reference": ref, "status": data.get("status")}
    except Exception as e:
        raise HTTPException(500, f"Verify failed: {e}")

@app.post("/v1/billing/cancel")
def billing_cancel(user_id: int = Depends(require_login)):
    """Cancel subscription effective immediately: status -> cancelled, trial metering resumes.
    Paystack-side disable happens via dashboard/webhook; no subscription code is stored to call disable.
    """
    db = get_db()
    user = get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("subscription_status") not in ("active", "trialing"):
        return {"ok": True, "status": user.get("subscription_status") or "free", "note": "No active subscription"}
    db.execute("UPDATE users SET subscription_status='cancelled' WHERE id=?", (user_id,))
    db.commit()
    append_audit_log(_tenant_of(user_id), user_id, "billing.cancel", "users", str(user_id), {"status": "cancelled"})
    return {"ok": True, "status": "cancelled"}

@app.post("/v1/webhooks/paystack")
async def paystack_webhook(request: Request):
    """
    Webhook with timing-safe HMAC SHA512 verify over the raw body.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    secret = get_paystack_sk()
    if not verify_paystack_signature(raw_body, signature, secret):
        raise HTTPException(400, "Invalid signature")

    try:
        payload = json.loads(raw_body)
    except:
        raise HTTPException(400, "Invalid JSON")

    event_type = payload.get("event", "")
    event_data = payload.get("data", {})

    # Idempotency via webhook_events
    db = get_db()
    event_id = event_data.get("id") or event_data.get("reference") or hashlib.sha256(raw_body).hexdigest()[:16]
    try:
        db.execute("INSERT INTO webhook_events (id, provider, event_id, signature_ok, payload_json) VALUES (?,?,?,?,?)", (event_id, "paystack", event_id, 1, json.dumps(payload)))
        db.commit()
    except:
        # Already processed - idempotent
        return {"ok": True, "dup": True}

    # Handle charge.success / subscription lifecycle events
    handle_webhook_event(event_type, event_data)

    return {"ok": True}

@app.get("/v1/audit")
def audit(object_type: Optional[str] = None, user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    if object_type:
        cur = db.execute("SELECT * FROM audit_log WHERE tenant_id=? AND object_type=? ORDER BY id DESC LIMIT 100", (tenant_id, object_type))
    else:
        cur = db.execute("SELECT * FROM audit_log WHERE tenant_id=? ORDER BY id DESC LIMIT 100", (tenant_id,))
    rows = cur.fetchall()
    return [dict(r) if not isinstance(r, dict) else r for r in rows]

@app.get("/v1/settings")
def get_settings(user_id: int = Depends(require_admin)):
    db = get_db()
    cur = db.execute("SELECT key, value FROM settings ORDER BY key")
    rows = cur.fetchall()
    # Filter out secret keys - redacted, never return actual secret
    forbidden_substrings = ["secret", "api_key", "password", "paystack"]
    result = {}
    for r in rows:
        k = r["key"] if isinstance(r, dict) else r[0]
        v = r["value"] if isinstance(r, dict) else r[1]
        # Redact secrets: show ***REDACTED*** + last4
        if any(sub in k.lower() for sub in forbidden_substrings):
            result[k] = "***REDACTED***" + (v[-4:] if len(v)>=4 else "")
        else:
            result[k] = v
    return result

class SettingsUpdateIn(BaseModel):
    key: str
    value: str

@app.post("/v1/settings")
def update_settings(inp: SettingsUpdateIn, user_id: int = Depends(require_admin)):
    # Forbid secret keys via API per docs/SETTINGS.md - must be env var (fail-closed)
    forbidden_exact = ["meta_api_key", "paystack_secret_key", "session_secret", "paystack_public_key", "paystack_plan_code", "paystack_plan_codes_json", "flask_secret"]
    if inp.key.lower() in forbidden_exact or "secret" in inp.key.lower():
        raise HTTPException(400, f"{inp.key} must be env var per security guide, not settings table (fail-closed)")
    # Allow only non-secret settings: model, effort, trial_pages, ollama_url, cost guards, privacy gate
    allowed_prefixes = ["model", "effort", "trial_", "ollama_url", "freellmapi_", "per_document_", "global_daily", "meta_rate_limit", "kill_switch", "show_exact", "ai_provider"]
    if not any(inp.key.lower().startswith(p) or inp.key.lower() == p for p in allowed_prefixes):
        # Still allow but log warning - for hackathon flexibility
        pass
    db = get_db()
    # Determine tenant for audit
    tenant_id = _tenant_of(user_id)
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (inp.key, inp.value))
    append_audit_log(tenant_id, user_id, "settings.update", "settings", inp.key, {"key": inp.key})
    db.commit()
    return {"ok": True, "key": inp.key, "value": inp.value if "secret" not in inp.key.lower() else "***REDACTED***"}



# Owner-safe preference keys (non-secret, non-billing). trial_/cost keys stay
# admin-only: an owner must not mint free uploads or lift rate guards.
OWNER_PREF_PREFIXES = ("model", "effort", "ai_provider", "ollama_url",
                       "freellmapi_", "show_exact")


@app.get("/v1/settings/preferences")
def get_preferences(user_id: int = Depends(require_owner_or_admin)):
    """Non-secret model/effort preferences for owners and admins.

    Never includes secret/billing keys - those live behind /v1/settings
    (admin-only)."""
    db = get_db()
    cur = db.execute("SELECT key, value FROM settings ORDER BY key")
    result = {}
    for r in cur.fetchall():
        k = r["key"] if isinstance(r, dict) else r[0]
        v = r["value"] if isinstance(r, dict) else r[1]
        kl = k.lower()
        if any(sub in kl for sub in ("secret", "api_key", "password", "paystack")):
            continue
        if kl.startswith(OWNER_PREF_PREFIXES) or kl in OWNER_PREF_PREFIXES:
            result[k] = v
    return result


@app.post("/v1/settings/preferences")
def update_preference(inp: SettingsUpdateIn,
                      user_id: int = Depends(require_owner_or_admin)):
    kl = inp.key.lower()
    forbidden_exact = ["meta_api_key", "paystack_secret_key", "session_secret",
                       "paystack_public_key", "paystack_plan_code",
                       "paystack_plan_codes_json", "flask_secret"]
    if kl in forbidden_exact or "secret" in kl:
        raise HTTPException(400, f"{inp.key} must be env var per security guide, "
                            "not settings table (fail-closed)")
    if not (kl.startswith(OWNER_PREF_PREFIXES) or kl in OWNER_PREF_PREFIXES):
        if not is_admin_user(user_id):
            raise HTTPException(403, f"{inp.key} is admin-only (billing/security key)")
    db = get_db()
    tenant_id = _tenant_of(user_id)
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
               (inp.key, inp.value))
    append_audit_log(tenant_id, user_id, "settings.preference", "settings",
                     inp.key, {"key": inp.key})
    db.commit()
    return {"ok": True, "key": inp.key, "value": inp.value}
@app.get("/privacy")
def privacy():
    # Serve real POPIA content from docs/legal/privacy.md
    doc_path = Path(__file__).parent.parent.parent / "docs" / "legal" / "privacy.md"
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else "Privacy - POPIA compliance, see docs/legal/privacy.md"
    return {"page": "privacy", "last_updated": "2026-10-26", "source": "docs/legal/privacy.md", "content_markdown": content[:5000], "full_path": str(doc_path), "compliance": "POPIA", "storage": "Railway/Supabase isolated by tenant_id+user_id", "ai_disclosure": "Meta standard tier no training, contributor only synthetic", "retention": "30 days deletion, legal_hold flag blocks deletion"}

@app.get("/terms")
def terms():
    doc_path = Path(__file__).parent.parent.parent / "docs" / "legal" / "terms.md"
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else "Terms"
    return {"page": "terms", "last_updated": "2026-10-26", "source": "docs/legal/terms.md", "content_markdown": content[:5000], "billing": "Free 20 uploads R0, Individual 200 R149/mo, SME 1000 R599/mo", "law": "South Africa", "ai_disclosure": "court-ready per ECTA s15, not guaranteed"}

@app.get("/refund")
def refund():
    doc_path = Path(__file__).parent.parent.parent / "docs" / "legal" / "refund.md"
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else "Refund"
    return {"page": "refund", "last_updated": "2026-10-26", "source": "docs/legal/refund.md", "content_markdown": content[:5000], "free_trial": "20 uploads", "exception": ">48h downtime pro-rata"}

@app.get("/ai-disclosure")
def ai_disclosure():
    doc_path = Path(__file__).parent.parent.parent / "docs" / "legal" / "ai_disclosure.md"
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else "AI Disclosure"
    return {"page": "ai-disclosure", "content_markdown": content[:8000], "models": ["muse-spark-1.3 standard NOT contributor", "muse-wonder-1.0", "muse-image-1.0", "sam-3.1"], "prompts_versioned": "prompts/*.md with SHA256 header", "anti_hallucination": "line-ID grounding + quote validation + reconciliation gate"}

# --- Vendor Rules per merchant per account - per user question: export vendor and add all transactions to certain account if like, sort and add rule, if certain code applies journal auto books other side
# For competition not lifetime project, per merchant per account rules for presentation layer vendor grouping and % allocation

class VendorRuleIn(BaseModel):
    normalized_merchant: str
    account_number: str
    target_account_id: str
    target_category_id: Optional[str] = None
    nature: str = "business"
    business_pct: int = 100
    auto_book: bool = False

@app.get("/v1/vendors")
def list_vendors(user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from .vendor import get_vendors
    vendors = get_vendors(tenant_id)
    return {"vendors": vendors, "count": len(vendors)}

@app.get("/v1/vendors/rules")
def list_vendor_rules(account_number: Optional[str] = None, user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    from .vendor import get_vendor_rules
    rules = get_vendor_rules(tenant_id, account_number)
    return {"rules": rules, "count": len(rules)}

@app.post("/v1/vendors/rules")
def create_vendor_rule_endpoint(inp: VendorRuleIn, user_id: int = Depends(require_login)):
    db = get_db()
    tenant_id = _tenant_of(user_id)
    # Extra manual validation so error message always says "Invalid parameters" (fixes bug report)
    if not inp.normalized_merchant or not inp.normalized_merchant.strip():
        raise HTTPException(422, "Invalid parameters: normalized_merchant is required")
    if not inp.account_number or not inp.account_number.strip():
        raise HTTPException(422, "Invalid parameters: account_number is required")
    if not inp.target_account_id or not inp.target_account_id.strip():
        raise HTTPException(422, "Invalid parameters: target_account_id is required")
    if inp.nature not in ("business", "private", "mixed", "unknown"):
        raise HTTPException(422, f"Invalid parameters: nature must be business|private|mixed|unknown, got '{inp.nature}'")
    if not isinstance(inp.business_pct, int) or not (0 <= inp.business_pct <= 100):
        raise HTTPException(422, f"Invalid parameters: business_pct must be int 0-100, got '{inp.business_pct}'")
    from .vendor import create_vendor_rule
    try:
        rule_id = create_vendor_rule(tenant_id, inp.normalized_merchant, inp.account_number, inp.target_account_id, inp.target_category_id, inp.nature, inp.business_pct, inp.auto_book, user_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"id": rule_id, "normalized_merchant": inp.normalized_merchant, "account_number": inp.account_number, "target_account_id": inp.target_account_id, "auto_book": inp.auto_book}

@app.post("/v1/vendors/rules/{rule_id}/apply")
def apply_vendor_rule(rule_id: str, user_id: int = Depends(require_login)):
    """
    If certain code applies journal auto books other side per user question
    Apply rule to all matching transactions for that merchant+account
    """
    db = get_db()
    tenant_id = _tenant_of(user_id)
    # Get rule
    cur = db.execute("SELECT * FROM vendor_rules WHERE id=? AND tenant_id=?", (rule_id, tenant_id))
    rule_row = cur.fetchone()
    if not rule_row:
        raise HTTPException(404, "Rule not found")
    rule = dict(rule_row) if not isinstance(rule_row, dict) else rule_row

    # Find matching transactions: description_raw ILIKE normalized_merchant AND account_number
    # For vendor export: export just a vendor if we do own set of books so user can export vendor and add all transactions to certain account
    cur = db.execute("SELECT id FROM transactions WHERE tenant_id=? AND account_number=? AND LOWER(description_raw) LIKE ?", (tenant_id, rule["account_number"], f"%{rule['normalized_merchant']}%"))
    txn_rows = cur.fetchall()
    applied = 0
    from .vendor import auto_book_journal_for_rule
    for r in txn_rows:
        txn_id = r["id"] if isinstance(r, dict) else r[0]
        try:
            if auto_book_journal_for_rule(txn_id, rule):
                applied += 1
        except Exception as e:
            # Skip if already balanced etc
            pass

    return {"rule_id": rule_id, "matched_transactions": len(txn_rows), "applied_journals": applied, "message": f"Applied rule {rule_id} to {applied}/{len(txn_rows)} transactions, journal auto books other side per code {rule.get('target_account_id')}"}


# --- Day4 Books: ledger-core + classify + review accept/edit (append-only revisions) ---
class JournalPostIn(BaseModel):
    transaction_id: str
    category_id: Optional[str] = None
    account_id: Optional[str] = None
    nature: str = "business"
    business_pct: int = 100


class ClassifySuggestIn(BaseModel):
    description: str
    account_number: str
    entity_kind: str = "personal"
    amount_minor: Optional[int] = None
    direction: Optional[str] = None


class ClassifyDecideIn(BaseModel):
    transaction_id: str
    nature: str
    business_pct: int = 100
    category_id: str
    rationale: str = ""
    reason: str


class ReviewAcceptIn(BaseModel):
    nature: Optional[str] = None
    business_pct: Optional[int] = None
    category_id: Optional[str] = None
    rationale: str = ""
    reason: str




class TxnMoveIn(BaseModel):
    to_code: str
    reason: str

class ReviewRejectIn(BaseModel):
    reason: str
class ReviewEditIn(BaseModel):
    description_raw: Optional[str] = None
    txn_date: Optional[str] = None
    amount_minor: Optional[int] = None
    nature: Optional[str] = None
    business_pct: Optional[int] = None
    category_id: Optional[str] = None
    rationale: str = ""
    reason: str


def _tenant_of(user_id: int) -> str:
    db = get_db()
    cur = db.execute("SELECT tenant_id FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    if isinstance(row, dict):
        return row.get("tenant_id") or "default-tenant"
    return row[0] if row else "default-tenant"


def _safe_name(value, fallback="file"):
    """Download filename fragment: alphanumerics only (traversal-proof)."""
    import re
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", str(value or ""))
    return cleaned[:32] or fallback


@app.post("/v1/journal/post")
def journal_post(inp: JournalPostIn, user_id: int = Depends(require_login)):
    tenant_id = _tenant_of(user_id)
    db = get_db()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (inp.transaction_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(
            422,
            f"Invalid parameters: transaction '{inp.transaction_id}' does not exist",
        )
    txn = dict(row) if not isinstance(row, dict) else row
    if txn.get("tenant_id") != tenant_id:
        raise HTTPException(403, "Cross-tenant access denied - isolation guard")
    from .ledger import post_transaction, UnknownAccount, UnbalancedEntry

    try:
        entry = post_transaction(
            txn,
            {
                "category_id": inp.category_id,
                "account_id": inp.account_id,
                "nature": inp.nature,
                "business_pct": inp.business_pct,
            },
            created_by=user_id,
        )
    except UnknownAccount as e:
        raise HTTPException(422, str(e))
    except UnbalancedEntry as e:
        raise HTTPException(422, f"Invalid parameters: {e}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    append_audit_log(
        tenant_id,
        user_id,
        "journal.post",
        "journal_entries",
        entry["id"],
        {"transaction_id": inp.transaction_id, "category_id": inp.category_id},
    )
    return entry


@app.get("/v1/journal/trial-balance")
def journal_trial_balance(
    as_of: Optional[str] = None,
    entity_id: Optional[str] = None,
    account_number: Optional[str] = None,
    user_id: int = Depends(require_login),
):
    tenant_id = _tenant_of(user_id)
    if as_of:
        _validate_period(as_of, as_of)
    from .ledger import trial_balance

    try:
        return trial_balance(tenant_id, as_of=as_of, entity_id=entity_id,
                             account_number=account_number)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/v1/journal/entries")
def journal_entries(
    transaction_id: Optional[str] = None,
    limit: int = 100,
    user_id: int = Depends(require_login),
):
    tenant_id = _tenant_of(user_id)
    from .ledger import get_journal_entries

    entries = get_journal_entries(tenant_id, transaction_id=transaction_id, limit=limit)
    return {"entries": entries, "count": len(entries)}


@app.get("/v1/journal/suspense")
def journal_suspense(user_id: int = Depends(require_login)):
    """9999 watchdog: suspense balance/count/aging vs thresholds + completeness check."""
    tenant_id = _tenant_of(user_id)
    from .ledger import suspense_status

    try:
        return suspense_status(tenant_id)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/v1/audit/human-changes")
def audit_human_changes(
    from_utc: Optional[str] = None,
    to_utc: Optional[str] = None,
    actor_id: Optional[int] = None,
    transaction_id: Optional[str] = None,
    limit: int = 100,
    user_id: int = Depends(require_login),
):
    """Legal record of every human change: revisions with old/new + reasons."""
    tenant_id = _tenant_of(user_id)
    from .audit import human_changes

    try:
        return human_changes(
            tenant_id,
            from_utc=from_utc,
            to_utc=to_utc,
            actor_id=actor_id,
            transaction_id=transaction_id,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/v1/audit/verify")
def audit_verify(user_id: int = Depends(require_login)):
    """Integrity proof: recompute audit hash chain + vault file hashes."""
    tenant_id = _tenant_of(user_id)
    from .audit import verify_integrity

    return verify_integrity(tenant_id)


@app.post("/v1/classifications/suggest")
def classify_suggest(inp: ClassifySuggestIn, user_id: int = Depends(require_login)):
    tenant_id = _tenant_of(user_id)
    from .classify import suggest_classification

    try:
        return suggest_classification(
            inp.description,
            inp.account_number,
            tenant_id,
            entity_kind=inp.entity_kind,
            amount_minor=inp.amount_minor,
            direction=inp.direction,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/v1/classifications/decide")
def classify_decide(inp: ClassifyDecideIn, user_id: int = Depends(require_login)):
    tenant_id = _tenant_of(user_id)
    from .classify import decide

    try:
        return decide(
            inp.transaction_id,
            inp.nature,
            inp.business_pct,
            inp.category_id,
            inp.rationale,
            user_id,
            inp.reason,
            tenant_id,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


def _load_owned_review_txn(txn_id: str, tenant_id: str) -> dict:
    """Load review transaction or raise 422/403 (existence + isolation)."""
    db = get_db()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(
            422, f"Invalid parameters: transaction '{txn_id}' does not exist"
        )
    txn = dict(row) if not isinstance(row, dict) else row
    if txn.get("tenant_id") != tenant_id:
        raise HTTPException(403, "Cross-tenant access denied - isolation guard")
    return txn


def _require_review_reason(reason: str) -> str:
    if not reason or not reason.strip():
        raise HTTPException(
            422, "Invalid parameters: reason is required for audit trail"
        )
    return reason.strip()


def _resolve_accept_classification(
    txn: dict, tenant_id: str, inp: ReviewAcceptIn
) -> tuple:
    """Fill missing accept classification from suggestion. Returns (nature, business_pct, category_id, rationale)."""
    from .classify import suggest_classification

    nature, category_id, rationale = inp.nature, inp.category_id, inp.rationale or ""
    business_pct = inp.business_pct if inp.business_pct is not None else 100
    if nature and category_id:
        return nature, business_pct, category_id, rationale
    try:
        sug = suggest_classification(
            txn.get("description_raw") or "",
            txn.get("account_number") or "",
            tenant_id,
            amount_minor=txn.get("amount_minor"),
            direction=txn.get("direction"),
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    nature = nature or sug["nature"]
    category_id = category_id or sug["category_id"]
    if inp.business_pct is None:
        business_pct = sug.get("business_pct", 100)
    return nature, business_pct, category_id, rationale or sug.get("rationale", "")


@app.post("/v1/review-queue/{txn_id}/accept")
def review_accept(
    txn_id: str, inp: ReviewAcceptIn, user_id: int = Depends(require_login)
):
    tenant_id = _tenant_of(user_id)
    db = get_db()
    txn = _load_owned_review_txn(txn_id, tenant_id)
    reason = _require_review_reason(inp.reason)
    from .classify import decide
    from .ledger import post_transaction, UnknownAccount, UnbalancedEntry

    nature, business_pct, category_id, rationale = _resolve_accept_classification(
        txn, tenant_id, inp
    )
    # Unknown is accepted into 9999 suspense (statements stay complete);
    # a later re-decide transfers the leg to the real account.
    if nature == "unknown" and not category_id:
        category_id = "9999"
    try:
        cls = decide(
            txn_id,
            nature,
            business_pct,
            category_id,
            rationale,
            user_id,
            reason,
            tenant_id,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        entry = post_transaction(
            txn,
            {
                "id": cls["id"],
                "category_id": category_id,
                "nature": nature,
                "business_pct": business_pct,
            },
            created_by=user_id,
        )
    except (UnknownAccount, UnbalancedEntry, ValueError) as e:
        raise HTTPException(
            422,
            str(e) if "Invalid parameters" in str(e) else f"Invalid parameters: {e}",
        )
    db.execute("UPDATE transactions SET status='confirmed' WHERE id=?", (txn_id,))
    db.commit()
    append_audit_log(
        tenant_id,
        user_id,
        "review.accept",
        "transactions",
        txn_id,
        {"classification_id": cls["id"], "entry_id": entry["id"]},
    )
    return {
        "transaction_id": txn_id,
        "status": "confirmed",
        "classification": cls,
        "journal_entry": entry,
    }


@app.post("/v1/transactions/{txn_id}/move")
def transaction_move(
    txn_id: str, inp: TxnMoveIn, user_id: int = Depends(require_login)
):
    """Re-decode a confirmed row (e.g. out of 9999 suspense): appends a
    new classification revision and transfers the posted leg. The review
    queue only shows unconfirmed rows, so this is the way back."""
    tenant_id = _tenant_of(user_id)
    txn = _load_owned_review_txn(txn_id, tenant_id)
    reason = _require_review_reason(inp.reason)
    from .ledger import transfer_posting, resolve_account, UnknownAccount
    from .classify import decide

    try:
        resolve_account(tenant_id, code=inp.to_code)
    except UnknownAccount as e:
        raise HTTPException(422, str(e))
    db = get_db()
    cur = db.execute(
        "SELECT * FROM classifications WHERE transaction_id=?"
        " AND tenant_id=? ORDER BY decided_at_utc DESC LIMIT 1",
        (txn_id, tenant_id),
    )
    row = cur.fetchone()
    prev = dict(row) if row is not None and not isinstance(row, dict) else row
    if prev is not None:
        from_code = prev.get("category_id")
        nature = prev.get("nature", "unknown")
        pct = prev.get("business_pct", 0)
    else:
        # Legacy orphan (pre-fix auto-book posted with no classification):
        # recover the posted leg's code from the journal itself.
        cur = db.execute(
            "SELECT a.code FROM journal_lines jl"
            " JOIN journal_entries je ON jl.entry_id=je.id"
            " JOIN accounts a ON jl.account_id=a.id"
            " WHERE je.transaction_id=? AND je.tenant_id=?"
            " AND jl.account_id != ? LIMIT 1",
            (txn_id, tenant_id, txn.get("account_id")),
        )
        r = cur.fetchone()
        if r is None:
            raise HTTPException(
                422,
                "Invalid parameters: nothing posted to move -"
                " accept the transaction first",
            )
        from_code = r["code"] if isinstance(r, dict) else r[0]
        nature, pct = "unknown", 0
    if from_code == inp.to_code:
        raise HTTPException(
            422,
            f"Invalid parameters: already on {inp.to_code} -"
            " nothing to move",
        )
    try:
        cls = decide(txn_id, nature, pct, inp.to_code,
                     f"Move {from_code}->{inp.to_code}", user_id,
                     reason, tenant_id)
        moved_id = cls.get("transfer_entry_id")
        if prev is None:
            # Legacy orphan: decide() had no previous code to move from,
            # so transfer the recovered posted leg explicitly.
            moved = transfer_posting(tenant_id, txn_id, from_code,
                                     inp.to_code, user_id, reason)
            moved_id = moved["id"] if moved else None
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    append_audit_log(
        tenant_id, user_id, "review.move", "transactions", txn_id,
        {"from_code": from_code, "to_code": inp.to_code,
         "classification_id": cls["id"]},
    )
    return {"transaction_id": txn_id, "from_code": from_code,
            "to_code": inp.to_code, "classification_id": cls["id"],
            "transfer_entry_id": moved_id}

@app.post("/v1/review-queue/{txn_id}/reject")
def review_reject(
    txn_id: str, inp: ReviewRejectIn, user_id: int = Depends(require_login)
):
    """Reject (proposed) or void (posted, via reversals). Append-only history."""
    tenant_id = _tenant_of(user_id)
    txn = _load_owned_review_txn(txn_id, tenant_id)
    reason = _require_review_reason(inp.reason)
    from .ledger import void_transaction

    try:
        out = void_transaction(tenant_id, txn_id, reason, created_by=user_id)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    append_audit_log(
        tenant_id,
        user_id,
        "review.reject",
        "transactions",
        txn_id,
        {"from_status": txn.get("status"), "reversed_entry_ids": out["reversed_entry_ids"]},
    )
    return out


def _collect_txn_updates(txn: dict, inp: ReviewEditIn) -> dict:
    """Validate edit fields and return {field: new_value} for changed fields only."""
    import re as _re

    if inp.txn_date and not _re.match(r"^\d{4}-\d{2}-\d{2}$", inp.txn_date):
        raise HTTPException(
            422,
            f"Invalid parameters: txn_date must be YYYY-MM-DD, got '{inp.txn_date}'",
        )
    if inp.amount_minor is not None and not isinstance(inp.amount_minor, int):
        raise HTTPException(
            422,
            f"Invalid parameters: amount_minor must be int cents, got '{inp.amount_minor}'",
        )
    updates: dict = {}
    if inp.description_raw is not None and inp.description_raw != txn.get(
        "description_raw"
    ):
        updates["description_raw"] = inp.description_raw
    if inp.txn_date is not None and inp.txn_date != txn.get("txn_date"):
        updates["txn_date"] = inp.txn_date
    if inp.amount_minor is not None and inp.amount_minor != txn.get("amount_minor"):
        updates["amount_minor"] = inp.amount_minor
    if not updates and not (inp.nature and inp.category_id):
        raise HTTPException(
            422,
            "Invalid parameters: nothing to edit - provide field changes and/or classification",
        )
    return updates


def _write_field_revisions(
    txn_id: str, tenant_id: str, txn: dict, updates: dict, reason: str, user_id: int
) -> list:
    """Insert one revision row per changed field. Returns revision ids."""
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    db = get_db()
    now = _dt.now(_tz.utc).isoformat()
    rev_ids: list = []
    for field, new_val in updates.items():
        rev_id = f"rev-{_uuid.uuid4().hex[:8]}"
        db.execute(
            "INSERT INTO transaction_revisions (id, tenant_id, transaction_id, field,"
            " old_value, new_value, reason, actor_id, at_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                rev_id,
                tenant_id,
                txn_id,
                field,
                str(txn.get(field)),
                str(new_val),
                reason,
                user_id,
                now,
            ),
        )
        rev_ids.append(rev_id)
    return rev_ids


def _apply_txn_updates(
    txn_id: str, tenant_id: str, txn: dict, updates: dict, reason: str, user_id: int
) -> dict:
    """Apply field updates atomically: revisions + row + fingerprint + journal repost.

    Amount/date changes on a posted txn reverse + repost its journals so every
    derived statement stays correct. Source rows (spans/vault/runs) are never
    touched. Returns {revisions, repost}. Rolls everything back on any failure.
    """
    db = get_db()
    try:
        rev_ids = _write_field_revisions(
            txn_id, tenant_id, txn, updates, reason, user_id
        )
        new_fp = fingerprint_txn(
            updates.get("txn_date", txn.get("txn_date")),
            updates.get("amount_minor", txn.get("amount_minor")),
            updates.get("description_raw", txn.get("description_raw") or ""),
        )
        set_clause = ", ".join(f"{k}=?" for k in updates) + ", fingerprint_sha256=?"
        params: list = list(updates.values()) + [new_fp, txn_id]
        try:
            db.execute(
                f"UPDATE transactions SET {set_clause} WHERE id=?", tuple(params)
            )
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                raise HTTPException(
                    422,
                    "Invalid parameters: edit would create duplicate transaction (fingerprint collision)",
                )
            raise
        repost = None
        if "amount_minor" in updates or "txn_date" in updates:
            from .ledger import repost_transaction

            try:
                repost = repost_transaction(
                    tenant_id, txn_id, reason, created_by=user_id, db=db
                )
            except PermissionError as e:
                raise HTTPException(403, str(e))
            except ValueError as e:
                raise HTTPException(
                    422,
                    str(e)
                    if "Invalid parameters" in str(e)
                    else f"Invalid parameters: {e}",
                )
        db.commit()
    except HTTPException:
        try:
            db.conn.rollback()
        except Exception:
            pass
        raise
    except Exception:
        try:
            db.conn.rollback()
        except Exception:
            pass
        raise
    return {"revisions": rev_ids, "repost": repost}


def _decide_edit_classification(
    txn_id: str, tenant_id: str, inp: ReviewEditIn, reason: str, user_id: int
):
    """Decide classification for an edit when nature+category provided, else None."""
    if not (inp.nature and inp.category_id):
        return None
    from .classify import decide

    try:
        return decide(
            txn_id,
            inp.nature,
            inp.business_pct if inp.business_pct is not None else 100,
            inp.category_id,
            inp.rationale or "",
            user_id,
            reason,
            tenant_id,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/v1/review-queue/{txn_id}/edit")
def review_edit(txn_id: str, inp: ReviewEditIn, user_id: int = Depends(require_login)):
    tenant_id = _tenant_of(user_id)
    txn = _load_owned_review_txn(txn_id, tenant_id)
    reason = _require_review_reason(inp.reason)
    updates = _collect_txn_updates(txn, inp)
    applied = (
        _apply_txn_updates(txn_id, tenant_id, txn, updates, reason, user_id)
        if updates
        else {"revisions": [], "repost": None}
    )
    rev_ids, repost = applied["revisions"], applied["repost"]
    cls = _decide_edit_classification(txn_id, tenant_id, inp, reason, user_id)
    if repost:
        append_audit_log(
            tenant_id,
            user_id,
            "journal.repost",
            "transactions",
            txn_id,
            {
                "reversed_entry_ids": repost["reversed_entry_ids"],
                "fresh_entry_id": repost["fresh_entry_id"],
                "fresh_category": repost["fresh_category"],
                "target_inferred": repost["target_inferred"],
                "reason": reason,
            },
        )
    reverify = None
    if "amount_minor" in updates or "txn_date" in updates:
        from .ledger import reverify_chain

        try:
            reverify = reverify_chain(tenant_id, txn_id)
        except ValueError as e:
            raise HTTPException(422, str(e))
        append_audit_log(
            tenant_id,
            user_id,
            "review.reverify",
            "transactions",
            txn_id,
            {
                "overall_pass": reverify["overall_pass"],
                "rows_checked": reverify["rows_checked"],
                "running_breaks": reverify["running_top_bottom"]["break_count"]
                + reverify["running_bottom_top"]["break_count"],
                "reason": reason,
            },
        )
    append_audit_log(
        tenant_id,
        user_id,
        "review.edit",
        "transactions",
        txn_id,
        {
            "revisions": rev_ids,
            "classification_id": cls["id"] if cls else None,
            "repost_entry_id": repost["fresh_entry_id"] if repost else None,
            "reverify_pass": reverify["overall_pass"] if reverify else None,
        },
    )
    return {
        "transaction_id": txn_id,
        "revisions": rev_ids,
        "updated_fields": sorted(updates),
        "classification": cls,
        "repost": repost,
        "reverification": reverify,
    }

