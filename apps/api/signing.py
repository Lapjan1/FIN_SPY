"""
PAdES report signing (Day 7): build a summary PDF from DB, sign with pyHanko,
timestamp via RFC3161 TSA when reachable. Nothing is faked: without a
configured certificate the endpoint refuses (422); without TSA the signature
goes out untimestamped with an explicit warning.
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

REPORTS_PATH = Path(os.getenv("REPORTS_PATH", "./data/reports"))
REPORTS_PATH.mkdir(parents=True, exist_ok=True)

TSA_DEFAULT_URL = "https://freetsa.org/tsr"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def signing_configured() -> bool:
    cert = os.getenv("FINSPY_SIGN_CERT", "")
    key = os.getenv("FINSPY_SIGN_KEY", "")
    return bool(cert and key and Path(cert).exists() and Path(key).exists())


def build_report_pdf(tenant_id: str, from_date: str | None, to_date: str | None,
                     out_path: Path) -> Dict:
    """One-page summary PDF from DB (pymupdf). Returns path/sha/pages."""
    import fitz
    from apps.api.db import get_db
    from apps.worker.spy.kpi import compute_period_totals

    db = get_db()
    q, p = "", [tenant_id]
    if from_date:
        q += " AND txn_date>=?"
        p.append(from_date)
    if to_date:
        q += " AND txn_date<=?"
        p.append(to_date)
    cur = db.execute("SELECT amount_minor, direction, txn_date FROM transactions"
                     " WHERE tenant_id=?" + q, tuple(p))
    txns = [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]
    totals = compute_period_totals(txns)
    cur = db.execute("SELECT COUNT(*) as n FROM accounts WHERE tenant_id=?", (tenant_id,))
    row = cur.fetchone()
    n_acc = row["n"] if isinstance(row, dict) else row[0]
    cur = db.execute("SELECT COUNT(*) as n FROM flags WHERE tenant_id=?", (tenant_id,))
    row = cur.fetchone()
    n_flags = row["n"] if isinstance(row, dict) else row[0]
    cur = db.execute("SELECT row_hash FROM audit_log WHERE tenant_id=?"
                     " ORDER BY id DESC LIMIT 1", (tenant_id,))
    row = cur.fetchone()
    head = (row["row_hash"] if isinstance(row, dict) else row[0]) if row else "none"

    def rands(minor: int) -> str:
        return f"R{minor / 100:,.2f}"

    doc = fitz.open()
    page = doc.new_page()
    lines = [
        "FIN_SPY Forensic Summary Report",
        f"Tenant: {tenant_id}",
        f"Period: {from_date or '...'} to {to_date or '...'}",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Transactions: {totals['txn_count']}",
        f"Inflow: {rands(totals['inflow_minor'])}  Outflow: {rands(totals['outflow_minor'])}",
        f"Net flow: {rands(totals['net_flow_minor'])}",
        f"Accounts: {n_acc}   Spy flags: {n_flags}",
        f"Audit head: {str(head)[:32]}",
        "",
        "Method: DB-first extraction, line-ID grounding, both-direction",
        "reconciliation, hash-chain audit. Money in minor units.",
        "Calculation aid, not financial advice.",
    ]
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 20
    doc.save(str(out_path))
    doc.close()
    return {"path": str(out_path), "sha256": _sha256_file(out_path), "pages": 1}


def _load_signer():
    from pyhanko.sign import signers
    cert = os.getenv("FINSPY_SIGN_CERT", "")
    key = os.getenv("FINSPY_SIGN_KEY", "")
    chain_raw = os.getenv("FINSPY_SIGN_CHAIN", "")
    chain = tuple(p for p in (c.strip() for c in chain_raw.split(",")) if p) if chain_raw else ()
    return signers.SimpleSigner.load(
        key, cert, ca_chain_files=chain,
        key_passphrase=os.getenv("FINSPY_SIGN_KEY_PASS", "").encode() or None)


def _stamper_or_none(url: str | None):
    if url is None:
        url = os.getenv("FINSPY_TSA_URL", TSA_DEFAULT_URL)
    if not url:
        return None
    try:
        from pyhanko.sign.timestamps import HTTPTimeStamper
        return HTTPTimeStamper(url)
    except Exception:
        return None


def sign_pdf_file(src: Path, dst: Path, tsa_url: str | None = "default") -> Dict:
    """PAdES-sign src into dst. Tries RFC3161 timestamp first; on TSA failure
    signs without and reports timestamped=False + warning (never silent)."""
    from pyhanko.sign import fields, signers
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    signer = _load_signer()
    stamper = _stamper_or_none(None if tsa_url == "default" else tsa_url)
    last_err: str | None = None
    for attempt, use_stamper in (("timestamped", stamper), ("plain", None)):
        if attempt == "timestamped" and stamper is None:
            continue
        try:
            with open(src, "rb") as inf:
                writer = IncrementalPdfFileWriter(inf)
                fields.append_signature_field(
                    writer, sig_field_spec=fields.SigFieldSpec("Signature1"))
                meta = signers.PdfSignatureMetadata(
                    field_name="Signature1",
                    location=os.getenv("FINSPY_SIGN_LOCATION", "South Africa"),
                    reason=os.getenv("FINSPY_SIGN_REASON", "FIN_SPY forensic report"),
                    contact_info="noreply@fin-spy.example")
                with open(dst, "wb") as outf:
                    signers.sign_pdf(writer, meta, signer=signer,
                                     timestamper=use_stamper, output=outf)
            return {"path": str(dst), "sha256": _sha256_file(dst),
                    "timestamped": use_stamper is not None,
                    "warning": last_err}
        except Exception as e:
            if use_stamper is None:
                raise RuntimeError(f"PAdES signing failed: {e}") from e
            last_err = f"timestamp omitted ({type(e).__name__}: {e})".strip()[:300]
            continue
    raise RuntimeError("PAdES signing failed: no attempt completed")


def verify_pdf_file(path: Path) -> Dict:
    """Validate embedded PAdES signature. Returns cryptographic validity
    separately from chain trust (self-signed test certs are valid+untrusted)."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    with open(path, "rb") as f:
        reader = PdfFileReader(f)
        sigs = list(reader.embedded_signatures)
        if not sigs:
            return {"signatures": 0, "valid": False, "trusted": False,
                    "signer": None}
        status = validate_pdf_signature(sigs[0])
    signer = None
    try:
        cert = status.signing_cert
        subj = cert.subject.human_friendly if hasattr(cert, "subject") else None
        signer = subj or str(getattr(cert, "human_friendly", cert))
    except Exception:
        signer = None
    return {"signatures": len(sigs), "valid": bool(status.valid),
            "intact": bool(status.intact), "trusted": bool(status.trusted),
            "signer": signer}


def build_and_sign(tenant_id: str, from_date: str | None,
                   to_date: str | None) -> Dict:
    from apps.api.reports import _validate_window

    if not signing_configured():
        raise ValueError("Invalid parameters: signing not configured"
                         " (FINSPY_SIGN_CERT/FINSPY_SIGN_KEY missing)")
    _validate_window(from_date, to_date)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unsigned = REPORTS_PATH / f"report_{tenant_id}_{ts}.pdf"
    signed = REPORTS_PATH / f"report_{tenant_id}_{ts}_signed.pdf"
    info = build_report_pdf(tenant_id, from_date, to_date, unsigned)
    sig = sign_pdf_file(unsigned, signed)
    out = {"unsigned": info, "signed": sig, "from_date": from_date,
           "to_date": to_date}
    out["file_key"] = sig["path"]
    out["sha256"] = sig["sha256"]
    return out
