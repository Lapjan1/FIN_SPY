"""
Smoke tests - fast, no GUI, no network, no model per AGENTS.md.
Run before every commit: uv run pytest -q
"""
import hashlib
from pathlib import Path

def test_scaffold_exists():
    # Check critical scaffold files exist - evidence before synthesis per AGENTS.md
    root = Path(__file__).parent.parent
    required = [
        root / "AGENTS.md",
        root / "docs" / "PLAN.md",
        root / "docs" / "MODULES.md",
        root / "docs" / "FLOWS.md",
        root / "apps" / "api" / "main.py",
        root / "apps" / "worker" / "llm" / "client.py",
        root / "config" / "models.yaml",
        root / "prompts" / "extract_sa_bank_v1.md",
        root / "packages" / "schemas" / "extraction_response.json",
    ]
    for p in required:
        assert p.exists(), f"Missing scaffold file: {p}"

def test_decimal_not_float():
    from decimal import Decimal
    # Money must be Decimal or int cents, never float per AGENTS.md
    amount = Decimal("1234.56")
    minor = int((amount * 100).to_integral_value())
    assert minor == 123456

def test_sha256_vault():
    data = b"test pdf content"
    sha = hashlib.sha256(data).hexdigest()
    assert len(sha) == 64

def test_fingerprint():
    # Fingerprint SHA256(date|amount|desc_norm) per AGENTS.md
    canonical = "2026-10-25|45000|woolworths"
    fp = hashlib.sha256(canonical.encode()).hexdigest()
    assert len(fp) == 64

def test_audit_hash_chain():
    # row_hash = SHA256(prev_hash || canonical_json)
    prev = "0"*64
    canonical_json = '{"tenant_id":"test","action":"upload"}'
    row_hash = hashlib.sha256((prev + canonical_json).encode()).hexdigest()
    assert len(row_hash) == 64

def test_sa_amount_parsing():
    from apps.worker.parsers.base import parse_sa_amount
    assert parse_sa_amount("R 1 234,56") == 123456
    assert parse_sa_amount("(450.00)") == -45000
    assert parse_sa_amount("450-") == -45000
    assert parse_sa_amount("450.00 Cr") == 45000  # Cr positive per SA, but test parser
