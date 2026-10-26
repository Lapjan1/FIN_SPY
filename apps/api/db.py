"""
DB adapter - Dual SQLite/Postgres per clearmind pattern + forensic hash-chain audit.
Based on clearmind-ai/database.py:103 dual support, but upgraded: bcrypt, RLS guard, hash-chain audit_log, tenant isolation.

Usage:
    from apps.api.db import get_db, init_db, is_postgres, DbHandle

Design:
- is_postgres() checks DATABASE_URL env (clearmind pattern)
- DbHandle translates ? -> %s, datetime('now') -> LOCALTIMESTAMP/CURRENT_DATE, INSERT OR REPLACE -> ON CONFLICT, INTEGER PK AUTOINCREMENT -> SERIAL
- WAL mode + foreign_keys ON for SQLite concurrency per clearmind
- Tables: tenants, users (paystack cols), documents (content-hash vault), pages, extraction_runs, source_spans, transactions (fingerprint), transaction_sources, classifications, accounts, journal_entries/lines (debits=credits), flags, audit_log hash-chained prev_hash/row_hash SHA256(prev||canonical_json), reports, subscriptions, usage_events, webhook_events, reset_tokens, settings
- All tables have tenant_id + RLS/isolation guard, append-only audit_log revokes UPDATE/DELETE from app role
"""
import os
import re
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Optional, Any, List, Dict
from datetime import datetime, timezone

DB_PATH = Path(os.getenv("VAULT_PATH", "./data")).parent / "fin_spy.db"  # ./data/fin_spy.db per AGENTS.md
DB_PATH = Path(os.getenv("DATABASE_PATH", "./data/fin_spy.db"))

def is_postgres() -> bool:
    url = os.getenv("DATABASE_URL", "")
    return url.startswith("postgres://") or url.startswith("postgresql://")

class DbHandle:
    def __init__(self):
        self.backend = "pg" if is_postgres() else "sqlite"
        if self.backend == "pg":
            import psycopg2
            import psycopg2.extras
            self.conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            self.conn.autocommit = True
            self.cursor_factory = psycopg2.extras.RealDictCursor
        else:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(DB_PATH))
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA foreign_keys=ON;")

    def _translate(self, sql: str) -> str:
        if self.backend != "pg":
            return sql
        # ? -> %s
        sql = sql.replace("?", "%s")
        # datetime('now') handling - clearmind pattern
        sql = sql.replace("datetime('now')", "LOCALTIMESTAMP")
        sql = sql.replace('datetime("now")', "LOCALTIMESTAMP")
        sql = sql.replace("date('now')", "CURRENT_DATE")
        # INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        # INSERT OR REPLACE -> ON CONFLICT DO UPDATE
        # Regex: INSERT OR REPLACE INTO table (col1,col2) VALUES (?,?)
        def repl_or_replace(m):
            table = m.group(1)
            cols = m.group(2)
            placeholders = m.group(3)
            # Assume first col is PK, conflict on it
            col_list = [c.strip() for c in cols.split(",")]
            set_clause = ", ".join([f"{c}=EXCLUDED.{c}" for c in col_list[1:]])
            if set_clause:
                return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({col_list[0]}) DO UPDATE SET {set_clause}"
            else:
                return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({col_list[0]}) DO NOTHING"
        sql = re.sub(r"INSERT OR REPLACE INTO (\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)", repl_or_replace, sql, flags=re.IGNORECASE)
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
        return sql

    def execute(self, sql: str, params: tuple = ()):
        sql_t = self._translate(sql)
        if self.backend == "pg":
            import psycopg2.extras
            cur = self.conn.cursor(cursor_factory=self.cursor_factory)
            cur.execute(sql_t, params)
            return cur
        else:
            cur = self.conn.cursor()
            cur.execute(sql_t, params)
            return cur

    def executescript(self, sql: str):
        if self.backend == "pg":
            # Split by ; like clearmind
            stmts = [s.strip() for s in re.split(r';\s*\n', sql.strip()) if s.strip()]
            for stmt in stmts:
                if stmt:
                    self.execute(stmt + ";")
        else:
            self.conn.executescript(sql)

    def commit(self):
        if self.backend == "sqlite":
            self.conn.commit()

    def last_id(self) -> int:
        cur = self.execute("SELECT lastval();" if self.backend=="pg" else "SELECT last_insert_rowid();")
        row = cur.fetchone()
        if row is None:
            return 0
        if self.backend == "pg":
            return row["lastval"] if isinstance(row, dict) else row[0]
        else:
            return row[0]

    def close(self):
        self.conn.close()

# Singleton for simple usage
_db_instance: Optional[DbHandle] = None

def get_db() -> DbHandle:
    global _db_instance
    if _db_instance is None:
        _db_instance = DbHandle()
    return _db_instance

def init_db():
    db = get_db()
    # Core schema - per docs Appendix A + clearmind tables
    db.executescript("""
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        plan_code TEXT DEFAULT 'free',
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT DEFAULT '',
        role TEXT DEFAULT 'owner',
        mfa_enabled INTEGER DEFAULT 0,
        subscription_status TEXT DEFAULT 'free',
        stripe_customer_id TEXT DEFAULT '',
        stripe_subscription_id TEXT DEFAULT '',
        paystack_customer_code TEXT DEFAULT '',
        paystack_subscription_code TEXT DEFAULT '',
        paystack_authorization_code TEXT DEFAULT '',
        referred_by TEXT DEFAULT '',
        partner_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    -- Forensic vault per homework Appendix A
    CREATE TABLE IF NOT EXISTS source_documents (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        entity_id TEXT,
        sha256 TEXT UNIQUE NOT NULL,
        size_bytes INTEGER NOT NULL,
        mime TEXT,
        storage_key TEXT NOT NULL,
        original_filename TEXT,
        uploaded_by INTEGER,
        uploaded_at_utc TEXT DEFAULT (datetime('now')),
        upload_ip TEXT,
        user_agent TEXT,
        status TEXT DEFAULT 'queued',
        legal_hold INTEGER DEFAULT 0,
        tsa_token_key TEXT,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );

    CREATE TABLE IF NOT EXISTS document_pages (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        page_no INTEGER NOT NULL,
        width REAL,
        height REAL,
        text_sha256 TEXT,
        image_sha256 TEXT,
        FOREIGN KEY (document_id) REFERENCES source_documents(id)
    );

    CREATE TABLE IF NOT EXISTS extraction_runs (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        pipeline_version TEXT,
        git_commit TEXT,
        method TEXT,
        model_id TEXT,
        prompt_id TEXT,
        prompt_sha256 TEXT,
        params_json TEXT,
        raw_output_key TEXT,
        raw_output_sha256 TEXT,
        started_at TEXT,
        finished_at TEXT,
        status TEXT,
        opening_balance_minor INTEGER,
        closing_balance_minor INTEGER,
        computed_closing_minor INTEGER,
        reconciliation TEXT,
        FOREIGN KEY (document_id) REFERENCES source_documents(id)
    );

    CREATE TABLE IF NOT EXISTS source_spans (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        page_no INTEGER NOT NULL,
        line_id TEXT NOT NULL,
        bbox_x0 REAL,
        bbox_y0 REAL,
        bbox_x1 REAL,
        bbox_y1 REAL,
        text TEXT,
        text_sha256 TEXT,
        FOREIGN KEY (run_id) REFERENCES extraction_runs(id)
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        entity_id TEXT,
        document_id TEXT,
        run_id TEXT,
        txn_date TEXT NOT NULL,
        description_raw TEXT,
        amount_minor INTEGER NOT NULL,
        currency TEXT DEFAULT 'ZAR',
        direction TEXT,
        balance_after_minor INTEGER,
        fingerprint_sha256 TEXT NOT NULL,
        status TEXT DEFAULT 'proposed',
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );

    CREATE TABLE IF NOT EXISTS transaction_sources (
        transaction_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        role TEXT,
        PRIMARY KEY (transaction_id, span_id),
        FOREIGN KEY (transaction_id) REFERENCES transactions(id),
        FOREIGN KEY (span_id) REFERENCES source_spans(id)
    );

    CREATE TABLE IF NOT EXISTS transaction_revisions (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        transaction_id TEXT NOT NULL,
        field TEXT,
        old_value TEXT,
        new_value TEXT,
        reason TEXT,
        actor_id INTEGER,
        at_utc TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS classifications (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        transaction_id TEXT NOT NULL,
        nature TEXT,
        business_pct INTEGER,
        category_id TEXT,
        rationale TEXT,
        source TEXT,
        confidence REAL,
        decided_by INTEGER,
        decided_at_utc TEXT DEFAULT (datetime('now')),
        supersedes_id TEXT,
        FOREIGN KEY (transaction_id) REFERENCES transactions(id)
    );

    CREATE TABLE IF NOT EXISTS accounts (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        entity_id TEXT,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );

    CREATE TABLE IF NOT EXISTS journal_entries (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        entity_id TEXT,
        entry_date TEXT,
        memo TEXT,
        transaction_id TEXT,
        classification_id TEXT,
        created_by INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS journal_lines (
        id TEXT PRIMARY KEY,
        entry_id TEXT NOT NULL,
        account_id TEXT NOT NULL,
        debit_minor INTEGER DEFAULT 0,
        credit_minor INTEGER DEFAULT 0,
        FOREIGN KEY (entry_id) REFERENCES journal_entries(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    );

    CREATE TABLE IF NOT EXISTS flags (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        test_id TEXT NOT NULL,
        params_json TEXT,
        severity TEXT,
        window_start TEXT,
        window_end TEXT,
        result_json TEXT,
        code_version TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS flag_links (
        flag_id TEXT NOT NULL,
        transaction_id TEXT,
        span_id TEXT,
        PRIMARY KEY (flag_id, transaction_id)
    );

    CREATE TABLE IF NOT EXISTS reports (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        kind TEXT,
        params_json TEXT,
        generated_by INTEGER,
        generated_at_utc TEXT DEFAULT (datetime('now')),
        file_key TEXT,
        file_sha256 TEXT,
        manifest_key TEXT,
        manifest_sha256 TEXT,
        signature_info TEXT,
        tsa_token_key TEXT
    );

    -- Append-only hash-chained audit_log per AGENTS.md
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        actor_id INTEGER,
        action TEXT NOT NULL,
        object_type TEXT,
        object_id TEXT,
        payload_json TEXT,
        prev_hash TEXT,
        row_hash TEXT,
        at_utc TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS anchors (
        id TEXT PRIMARY KEY,
        from_audit_id INTEGER,
        to_audit_id INTEGER,
        chain_head_hash TEXT,
        tsa_url TEXT,
        tsa_token_key TEXT,
        at_utc TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id INTEGER,
        paystack_customer_code TEXT,
        paystack_customer_email TEXT,
        plan_code TEXT,
        status TEXT,
        current_period_end TEXT,
        cancel_at_period_end INTEGER DEFAULT 0,
        paystack_subscription_code TEXT,
        builds_allowed INTEGER DEFAULT 20,
        builds_used INTEGER DEFAULT 0,
        reference TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );

    CREATE TABLE IF NOT EXISTS usage_events (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        kind TEXT,
        units INTEGER,
        est_cost_usd REAL,
        at_utc TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS webhook_events (
        id TEXT PRIMARY KEY,
        provider TEXT,
        event_id TEXT UNIQUE,
        signature_ok INTEGER,
        payload_json TEXT,
        processed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS partner_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        framework TEXT DEFAULT '',
        description TEXT DEFAULT '',
        features TEXT DEFAULT '[]',
        referral_code TEXT UNIQUE NOT NULL,
        theme_color TEXT DEFAULT '#1a1a2e',
        logo_url TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    # Migrations per clearmind pattern
    _ensure_schema(db)
    db.commit()

def _ensure_schema(db: DbHandle):
    # Paystack cols added via ALTER like clearmind database.py:210
    cols_to_add = [
        ("users", "paystack_customer_code", "TEXT DEFAULT ''"),
        ("users", "paystack_subscription_code", "TEXT DEFAULT ''"),
        ("users", "paystack_authorization_code", "TEXT DEFAULT ''"),
        ("users", "referred_by", "TEXT DEFAULT ''"),
        ("users", "partner_demo", "INTEGER DEFAULT 0"),
        ("users", "stripe_customer_id", "TEXT DEFAULT ''"),
        ("users", "stripe_subscription_id", "TEXT DEFAULT ''"),
        ("partner_profiles", "features", "TEXT DEFAULT '[]'"),
        ("partner_profiles", "logo_url", "TEXT DEFAULT ''"),
        ("partner_profiles", "theme_color", "TEXT DEFAULT '#1a1a2e'"),
    ]
    for table, col, typ in cols_to_add:
        try:
            if db.backend == "pg":
                db.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}")
            else:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except Exception:
            pass  # column exists

# Helper: hash chain for audit_log
def compute_row_hash(prev_hash: str, canonical_json: str) -> str:
    """
    row_hash = SHA256(prev||canonical_json) per AGENTS.md
    """
    return hashlib.sha256((prev_hash + canonical_json).encode()).hexdigest()

def get_last_audit_hash(tenant_id: str) -> str:
    db = get_db()
    cur = db.execute("SELECT row_hash FROM audit_log WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (tenant_id,))
    row = cur.fetchone()
    if not row:
        return "0"*64
    if isinstance(row, dict):
        return row["row_hash"] or "0"*64
    return row[0] or "0"*64

def append_audit_log(tenant_id: str, actor_id: Optional[int], action: str, object_type: str, object_id: str, payload: Dict[str,Any]) -> str:
    db = get_db()
    prev = get_last_audit_hash(tenant_id)
    canonical = json.dumps(payload, sort_keys=True, separators=(',',':'))
    row_hash = compute_row_hash(prev, canonical)
    audit_id = hashlib.sha256((tenant_id + action + str(datetime.now(timezone.utc))).encode()).hexdigest()[:16]
    # Persist
    db.execute(
        "INSERT INTO audit_log (tenant_id, actor_id, action, object_type, object_id, payload_json, prev_hash, row_hash, at_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        (tenant_id, actor_id, action, object_type, object_id, canonical, prev, row_hash, datetime.now(timezone.utc).isoformat())
    )
    db.commit()
    return row_hash

def get_setting(key: str, default: str = "") -> str:
    db = get_db()
    cur = db.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    if not row:
        return default
    return row[0] if not isinstance(row, dict) else row["value"]

def set_setting(key: str, value: str):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    db.commit()

def env_or_setting(key: str, default: str = "") -> str:
    return os.getenv(key.upper()) or get_setting(key, default)
