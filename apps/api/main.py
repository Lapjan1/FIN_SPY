"""
FastAPI API - DB-first: Extract -> persist to .db -> all products read from DB.
Per AGENTS.md commands: uv run fastapi dev apps/api/main.py --port 8000
"""
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import List, Optional
import hashlib
import os
from pathlib import Path

app = FastAPI(
    title="FIN_SPY API",
    version="0.1.0",
    description="Financial Surveillance & Peak Insights - DB-first forensic books + spy + KPIs + debt strategies. Built with Meta Muse."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic models (Decimal not float per AGENTS.md) ---
class TransactionOut(BaseModel):
    id: str
    tenant_id: str
    txn_date: str
    description_raw: str
    amount_minor: int  # cents
    direction: str
    balance_after_minor: Optional[int] = None
    fingerprint_sha256: str
    status: str
    doc_id: str
    page_no: int
    line_ids: List[str]

class DashboardSummary(BaseModel):
    leak_score_per_month_minor: int
    runway_months: float
    burn_rate_minor: int
    savings_rate_pct: float
    private_vs_business_ratio: float

class DebtInput(BaseModel):
    creditor: str
    balance_minor: int
    apr_pct: Decimal = Field(..., description="Annual APR as decimal e.g. 21 for 21%")
    min_payment_minor: int

class DebtPlanRequest(BaseModel):
    debts: List[DebtInput]
    method: str = Field(..., pattern="^(snowball|avalanche)$")
    extra_cash_per_month_minor: int = 0

class ChatRequest(BaseModel):
    messages: List[dict]
    tenant_id: str

# --- Helpers ---
VAULT_PATH = Path(os.getenv("VAULT_PATH", "./data/vault"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fingerprint_txn(date: str, amount_minor: int, desc_norm: str) -> str:
    canonical = f"{date}|{amount_minor}|{desc_norm.lower().strip()}"
    return hashlib.sha256(canonical.encode()).hexdigest()

# --- Routes per docs/decision Appendix E ---
@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0", "db_first": True}

@app.post("/v1/documents")
async def upload_document(file: UploadFile = File(...), tenant_id: str = "demo-tenant"):
    """
    Intake vault: hash SHA256, store content-addressed immutable, audit log hash-chain, enqueue job.
    """
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large >50MB")
    if not file.filename.lower().endswith(('.pdf','.csv','.ofx','.jpg','.jpeg','.png')):
        raise HTTPException(400, "Unsupported type")
    sha = sha256_bytes(data)
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    storage_key = VAULT_PATH / f"{sha}.pdf"
    if not storage_key.exists():
        storage_key.write_bytes(data)
        # TODO: append audit_log with prev_hash/row_hash SHA256(prev||canonical_json) per AGENTS.md
        # TODO: enqueue Procrastinate job
    return {
        "id": sha[:12],
        "sha256": sha,
        "storage_key": str(storage_key),
        "original_filename": file.filename,
        "size_bytes": len(data),
        "status": "queued",
        "tenant_id": tenant_id
    }

@app.get("/v1/transactions")
def list_transactions(tenant_id: str = "demo-tenant", status: Optional[str] = None) -> List[TransactionOut]:
    # TODO: read from SQLite fin_spy.db, not from extraction directly - DB-first per AGENTS.md
    # Mock return for scaffold
    return []

@app.get("/v1/transactions/{txn_id}/sources")
def get_sources(txn_id: str):
    # Returns page_no + bbox for highlight overlay - signature demo
    return {"txn_id": txn_id, "page_no": 1, "line_ids": ["L012"], "bboxes": [{"line_id":"L012","x0":10,"y0":20,"x1":90,"y1":25}]}

@app.get("/v1/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(tenant_id: str = "demo-tenant"):
    # TODO: compute from DB kpi-engine
    return DashboardSummary(
        leak_score_per_month_minor=18700,  # R187.00
        runway_months=4.5,
        burn_rate_minor=2500000,
        savings_rate_pct=12.5,
        private_vs_business_ratio=0.35
    )

@app.get("/v1/flags")
def flags(tenant_id: str = "demo-tenant"):
    # Forensic flags F-001..F-050
    return []

@app.post("/v1/debt/plan")
def debt_plan(req: DebtPlanRequest):
    """
    Debt snowball vs avalanche - pure Decimal math, never float.
    """
    # TODO: implement in apps/worker/spy/debt.py with Decimal
    # Placeholder orders
    if req.method == "snowball":
        order = sorted(req.debts, key=lambda d: d.balance_minor)
    else:
        order = sorted(req.debts, key=lambda d: d.apr_pct, reverse=True)
    return {"method": req.method, "order": [d.creditor for d in order], "months": 12, "interest_saved_minor": 0, "total_paid_minor": sum(d.balance_minor for d in order)}

@app.post("/v1/chat")
def chat(req: ChatRequest):
    """
    Spy Chat with tool calling over DB - must cite evidence, no hallucination.
    Uses llm-client router local-first.
    """
    # TODO: call apps/worker/llm/client.py with tools: search_transactions, explain_flag, debt_plan
    return {"answer": "Mock: Your Woolworths spend R1200 last month, 2x duplicate subscription detected R89.99, see doc a1b2 page 3 L012.", "tool_calls": [], "citations": []}

@app.post("/v1/reports")
def create_report(kind: str = "excel", tenant_id: str = "demo-tenant"):
    # Excel/PDF/pack/powerbi per Appendix E
    return {"id": "report_123", "kind": kind, "status": "queued"}

@app.get("/v1/reports/{report_id}")
def get_report(report_id: str):
    return {"id": report_id, "file_key": f"reports/{report_id}.pdf", "sha256": "abc", "status": "ready"}

@app.post("/v1/billing/checkout")
def billing_checkout(plan_code: str = "individual"):
    # Paystack test mode per docs - initialize transaction server-side, never trust redirect, rely on webhook
    return {"checkout_url": "https://paystack.com/pay/test", "plan_code": plan_code}

@app.post("/v1/webhooks/paystack")
def paystack_webhook():
    # TODO: verify x-paystack-signature HMAC SHA512 raw body, idempotent
    return {"ok": True}

@app.get("/v1/audit")
def audit(object_type: Optional[str] = None):
    # Read-only audit log for verification
    return []
