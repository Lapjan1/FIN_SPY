"""
Worker - Procrastinate SQLite queue (MVP) -> Postgres prod per AGENTS.md
Per docs: intake -> hash -> store -> text/OCR -> extract -> reconcile -> classify -> post -> analytics -> reports
DB-first: every step persists to .db before next.
"""
import os
from pathlib import Path

def main():
    print("FIN_SPY worker starting...")
    print("Vault:", os.getenv("VAULT_PATH", "./data/vault"))
    print("DB:", os.getenv("DATABASE_URL", "sqlite:///./data/fin_spy.db"))
    print("Meta base:", os.getenv("FREELLMAPI_BASE_URL", "http://127.0.0.1:3001/v1"))
    print("Queue: sqlite MVP, Postgres prod via Procrastinate")
    print("TODO: start Procrastinate worker, global rate limiter 100 RPM, per-tenant fairness")
    print("Forensic pipeline: intake->hash->text+bbox->deterministic->LLM fallback line-ID grounding->validate->persist")
    print("Reference extractor with 25+ adaptors can be READ per AGENTS.md at FNBP_REFERENCE_PATH, never imported")
    # TODO: implement pipeline

if __name__ == "__main__":
    main()
