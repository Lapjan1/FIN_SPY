"""
DB adapter - dual SQLite/Postgres + forensic hash-chain audit.
Prior art: docs/AUTH_PAYSTACK.md. Upgraded: bcrypt, RLS guard, hash-chain audit_log, tenant isolation.

Usage:
    from apps.api.db import get_db, init_db, is_postgres, DbHandle

Design:
- is_postgres() checks DATABASE_URL env
- DbHandle translates ? -> %s, datetime('now') -> LOCALTIMESTAMP/CURRENT_DATE, INSERT OR REPLACE -> ON CONFLICT, INTEGER PK AUTOINCREMENT -> SERIAL
- WAL mode + foreign_keys ON for SQLite concurrency
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
            # check_same_thread=False for FastAPI TestClient multi-thread + threading issue fix
            self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA foreign_keys=ON;")
            self.conn.execute("PRAGMA busy_timeout=5000;")

    def _translate(self, sql: str) -> str:
        if self.backend != "pg":
            return sql
        # ? -> %s
        sql = sql.replace("?", "%s")
        # datetime('now') handling for SQLite/Postgres translate
        sql = sql.replace("datetime('now')", "LOCALTIMESTAMP")
        sql = sql.replace('datetime("now")', "LOCALTIMESTAMP")
        sql = sql.replace("date('now')", "CURRENT_DATE")
        # INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        # INSERT OR REPLACE -> ON CONFLICT DO UPDATE
        # Regex: INSERT OR REPLACE INTO table (col1,col2) VALUES (?,?)
        # Most tables are first-col PK; composite keys are pinned here -
        # a wrong target is Postgres 42P10 InvalidColumnReference.
        conflict_targets = {"transaction_sources": "(transaction_id, span_id)"}
        def repl_or_replace(m):
            table = m.group(1)
            cols = m.group(2)
            placeholders = m.group(3)
            col_list = [c.strip() for c in cols.split(",")]
            target = conflict_targets.get(table.lower(), f"({col_list[0]})")
            set_clause = ", ".join([f"{c}=EXCLUDED.{c}" for c in col_list[1:]])
            if set_clause:
                return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT {target} DO UPDATE SET {set_clause}"
            else:
                return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT {target} DO NOTHING"
        sql = re.sub(r"INSERT OR REPLACE INTO (\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)", repl_or_replace, sql, flags=re.IGNORECASE)
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
        # strftime() -> EXTRACT for dim_date (cols are TEXT 'YYYY-MM-DD').
        # DOW matches sqlite %w exactly (0=Sunday..6=Saturday).
        sql = re.sub(
            r"CAST\(strftime\('%Y',\s*(\w+)\) AS INTEGER\)",
            r"EXTRACT(YEAR FROM \1::date)::INTEGER", sql)
        sql = re.sub(
            r"CAST\(strftime\('%m',\s*(\w+)\) AS INTEGER\)",
            r"EXTRACT(MONTH FROM \1::date)::INTEGER", sql)
        sql = re.sub(
            r"CAST\(strftime\('%d',\s*(\w+)\) AS INTEGER\)",
            r"EXTRACT(DAY FROM \1::date)::INTEGER", sql)
        sql = re.sub(
            r"CAST\(strftime\('%w',\s*(\w+)\) AS INTEGER\)",
            r"EXTRACT(DOW FROM \1::date)::INTEGER", sql)
        sql = re.sub(
            r"CAST\(\(strftime\('%m',\s*(\w+)\)\+2\)/3 AS INTEGER\)",
            r"EXTRACT(QUARTER FROM \1::date)::INTEGER", sql)
        sql = sql.replace(
            "CREATE VIEW IF NOT EXISTS", "CREATE OR REPLACE VIEW")
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
            # Split by ;. Trigger DDL is sqlite-only: pg skips
            # it (app-level post_transaction validation covers pg instead).
            # Each statement runs independently with loud warnings so one bad
            # view/trigger can never take down boot again (Oct28 crash).
            stmts = [s.strip() for s in re.split(r';\s*\n', sql.strip()) if s.strip()]
            for stmt in stmts:
                # Strip full-line `--` comments: a literal % or ? inside a
                # comment reaches psycopg2 param substitution and aborts the
                # whole statement (prod: merchant_memory never created).
                stmt = "\n".join(
                    ln for ln in stmt.splitlines()
                    if not ln.strip().startswith("--")
                ).strip()
                if not stmt:
                    continue
                if re.search(r"\b(CREATE|DROP)\s+TRIGGER\b", stmt, re.I):
                    continue
                try:
                    self.execute(stmt + ";")
                except Exception as e:
                    print(
                        f"WARN: pg schema statement failed, continuing:"
                        f" {stmt[:100]!r} -> {e}"
                    )
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
    # Core schema - per docs Appendix A
    db.executescript("""
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        plan_code TEXT DEFAULT 'free',
        status TEXT DEFAULT 'active',
        active_template TEXT DEFAULT 'personal',
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
        account_id TEXT,
        account_number TEXT,
        bank_name TEXT,
        branch_code TEXT,
        sha256 TEXT NOT NULL,
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
        UNIQUE(tenant_id, sha256),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id)
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
        page_width REAL,
        page_height REAL,
        text TEXT,
        text_sha256 TEXT,
        FOREIGN KEY (run_id) REFERENCES extraction_runs(id)
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        entity_id TEXT,
        account_id TEXT,
        account_number TEXT,
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
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id),
        FOREIGN KEY (document_id) REFERENCES source_documents(id),
        UNIQUE(tenant_id, account_number, fingerprint_sha256)
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
        account_number TEXT,
        bank_name TEXT,
        branch_code TEXT,
        is_active INTEGER DEFAULT 1,
        template TEXT DEFAULT 'personal',
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        UNIQUE(tenant_id, account_number)
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
        posted INTEGER DEFAULT 0,
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

    -- Merchant memory / vendor rules per merchant per account per user question: export vendor and add all transactions to certain account if like, sort and add rule, if certain code applies journal auto books other side
    -- For competition not lifetime project, per merchant per account rules for presentation layer vendor grouping and % allocation
    CREATE TABLE IF NOT EXISTS merchant_memory (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        normalized_merchant TEXT NOT NULL,
        account_number TEXT,
        account_id TEXT,
        category_id TEXT,
        nature TEXT,
        business_pct INTEGER DEFAULT 100,
        rationale TEXT,
        source TEXT DEFAULT 'rule',
        confidence REAL DEFAULT 1.0,
        decided_by INTEGER,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id),
        UNIQUE(tenant_id, normalized_merchant, account_number)
    );

    CREATE TABLE IF NOT EXISTS vendor_rules (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        normalized_merchant TEXT NOT NULL,
        account_number TEXT NOT NULL,
        target_account_id TEXT NOT NULL,
        target_category_id TEXT,
        nature TEXT,
        business_pct INTEGER DEFAULT 100,
        auto_book INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id),
        FOREIGN KEY (target_account_id) REFERENCES accounts(id),
        UNIQUE(tenant_id, normalized_merchant, account_number)
    );

    -- Indexes for performance per homework Done Means: 1000 tx analyze <5s without LLM, <15s with LLM, PowerBI export
    CREATE INDEX IF NOT EXISTS idx_transactions_tenant_date ON transactions(tenant_id, txn_date);
    CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(fingerprint_sha256);
    CREATE INDEX IF NOT EXISTS idx_transactions_document ON transactions(document_id);
    CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
    CREATE INDEX IF NOT EXISTS idx_source_documents_tenant_sha ON source_documents(tenant_id, sha256);
    CREATE INDEX IF NOT EXISTS idx_source_documents_uploaded_by ON source_documents(uploaded_by);
    CREATE INDEX IF NOT EXISTS idx_source_spans_tenant_doc ON source_spans(tenant_id, document_id);
    CREATE INDEX IF NOT EXISTS idx_source_spans_run ON source_spans(run_id);
    CREATE INDEX IF NOT EXISTS idx_classifications_tenant_txn ON classifications(tenant_id, transaction_id);
    CREATE INDEX IF NOT EXISTS idx_classifications_category ON classifications(category_id);
    CREATE INDEX IF NOT EXISTS idx_journal_entries_tenant_date ON journal_entries(tenant_id, entry_date);
    CREATE INDEX IF NOT EXISTS idx_journal_lines_entry ON journal_lines(entry_id);
    CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_id);
    CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_object ON audit_log(tenant_id, object_type, object_id);
    CREATE INDEX IF NOT EXISTS idx_flags_tenant_test ON flags(tenant_id, test_id);
    CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_kind ON usage_events(tenant_id, kind);
    CREATE INDEX IF NOT EXISTS idx_document_pages_doc ON document_pages(document_id);
    CREATE INDEX IF NOT EXISTS idx_extraction_runs_doc ON extraction_runs(document_id);
    CREATE INDEX IF NOT EXISTS idx_transaction_sources_txn ON transaction_sources(transaction_id);
    CREATE INDEX IF NOT EXISTS idx_transaction_sources_span ON transaction_sources(span_id);

    -- Star-schema views for PowerBI export per homework Part 5.10: fact_transactions, fact_journal, dim_account, dim_category, dim_entity, dim_document, dim_date
    -- dim_date as view (not table) to avoid conflict - generates calendar from transactions + journal_entries
    CREATE VIEW IF NOT EXISTS fact_transactions AS
        SELECT t.id, t.tenant_id, t.entity_id, t.account_id, t.account_number, t.document_id, t.run_id, t.txn_date as date, t.description_raw, t.amount_minor, t.currency, t.direction, t.balance_after_minor, t.fingerprint_sha256, t.status, c.nature, c.business_pct, c.category_id, c.rationale, c.confidence
        FROM transactions t LEFT JOIN classifications c ON t.id = c.transaction_id;

    CREATE VIEW IF NOT EXISTS fact_journal AS
        SELECT je.id as entry_id, je.tenant_id, je.entity_id, je.entry_date as date, je.memo, je.transaction_id, je.classification_id, jl.id as line_id, jl.account_id, jl.debit_minor, jl.credit_minor, a.code as account_code, a.name as account_name, a.type as account_type
        FROM journal_entries je JOIN journal_lines jl ON je.id = jl.entry_id LEFT JOIN accounts a ON jl.account_id = a.id;

    CREATE VIEW IF NOT EXISTS dim_account AS
        SELECT id, tenant_id, entity_id, code, name, type FROM accounts;

    CREATE VIEW IF NOT EXISTS dim_category AS
        SELECT DISTINCT category_id as id, category_id as name FROM classifications WHERE category_id IS NOT NULL
        UNION
        SELECT DISTINCT '6000' as id, 'Marketing' as name UNION SELECT '6100','Rent' UNION SELECT '6200','Fuel' UNION SELECT '6600','Bank Charges' UNION SELECT '7000','Drawings';

    CREATE VIEW IF NOT EXISTS dim_entity AS
        SELECT id, name, plan_code, status FROM tenants
        UNION
        SELECT entity_id as id, entity_id as name, '' as plan_code, 'active' as status FROM (SELECT DISTINCT entity_id as entity_id FROM transactions WHERE entity_id IS NOT NULL) AS sub;

    CREATE VIEW IF NOT EXISTS dim_document AS
        SELECT id, tenant_id, sha256, original_filename, size_bytes, mime, uploaded_at_utc, status, legal_hold FROM source_documents;

    CREATE VIEW IF NOT EXISTS dim_date AS
        SELECT DISTINCT txn_date as date,
               CAST(strftime('%Y', txn_date) AS INTEGER) as year,
               CAST(strftime('%m', txn_date) AS INTEGER) as month,
               CAST(strftime('%d', txn_date) AS INTEGER) as day,
               CAST((strftime('%m', txn_date)+2)/3 AS INTEGER) as quarter,
               CASE CAST(strftime('%m', txn_date) AS INTEGER)
                 WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March' WHEN 4 THEN 'April'
                 WHEN 5 THEN 'May' WHEN 6 THEN 'June' WHEN 7 THEN 'July' WHEN 8 THEN 'August'
                 WHEN 9 THEN 'September' WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December'
               END as month_name,
               CAST(strftime('%w', txn_date) AS INTEGER) as day_of_week,
               CASE WHEN CAST(strftime('%w', txn_date) AS INTEGER) IN (0,6) THEN 1 ELSE 0 END as is_weekend
        FROM transactions
        UNION
        SELECT DISTINCT entry_date as date,
               CAST(strftime('%Y', entry_date) AS INTEGER) as year,
               CAST(strftime('%m', entry_date) AS INTEGER) as month,
               CAST(strftime('%d', entry_date) AS INTEGER) as day,
               CAST((strftime('%m', entry_date)+2)/3 AS INTEGER) as quarter,
               CASE CAST(strftime('%m', entry_date) AS INTEGER)
                 WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March' WHEN 4 THEN 'April'
                 WHEN 5 THEN 'May' WHEN 6 THEN 'June' WHEN 7 THEN 'July' WHEN 8 THEN 'August'
                 WHEN 9 THEN 'September' WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December'
               END as month_name,
               CAST(strftime('%w', entry_date) AS INTEGER) as day_of_week,
               CASE WHEN CAST(strftime('%w', entry_date) AS INTEGER) IN (0,6) THEN 1 ELSE 0 END as is_weekend
        FROM journal_entries WHERE entry_date IS NOT NULL;

    -- Journal balance constraint: debits = credits per POSTED entry (double-entry) per AGENTS.md ledger-core
    -- Day4 fix: old count>=2 prefix check made legal 3-line mixed splits impossible (any 2-line
    -- prefix of Dr+Dr/Cr is unbalanced). New mechanism: draft lines freely while posted=0,
    -- balance enforced when posting (UPDATE posted=1) and lines of posted entries stay guarded.
    DROP TRIGGER IF EXISTS trg_journal_balance_check_insert;
    DROP TRIGGER IF EXISTS trg_journal_balance_check_update;
    DROP TRIGGER IF EXISTS trg_journal_balance_check_delete;
    CREATE TRIGGER IF NOT EXISTS trg_journal_lines_guard_insert
    AFTER INSERT ON journal_lines
    FOR EACH ROW
    WHEN (SELECT posted FROM journal_entries WHERE id=NEW.entry_id) = 1
    BEGIN
        SELECT CASE WHEN (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT COALESCE(SUM(credit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id)
        THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits (posted entry)')
        END;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_journal_lines_guard_update
    AFTER UPDATE ON journal_lines
    FOR EACH ROW
    WHEN (SELECT posted FROM journal_entries WHERE id=NEW.entry_id) = 1
    BEGIN
        SELECT CASE WHEN (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT COALESCE(SUM(credit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id)
        THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits (posted entry)')
        END;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_journal_lines_guard_delete
    AFTER DELETE ON journal_lines
    FOR EACH ROW
    WHEN (SELECT posted FROM journal_entries WHERE id=OLD.entry_id) = 1
    BEGIN
        SELECT CASE WHEN (SELECT COUNT(*) FROM journal_lines WHERE entry_id=OLD.entry_id) > 0
        THEN RAISE(ABORT, 'Journal entry not balanced after delete: cannot remove lines from a posted entry (unpost first)')
        END;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_journal_entry_post
    AFTER UPDATE OF posted ON journal_entries
    FOR EACH ROW
    WHEN NEW.posted = 1
    BEGIN
        SELECT CASE WHEN (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.id) < 2
        THEN RAISE(ABORT, 'Journal entry not balanced: need at least 2 lines to post')
        END;
        SELECT CASE WHEN (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines WHERE entry_id=NEW.id) != (SELECT COALESCE(SUM(credit_minor),0) FROM journal_lines WHERE entry_id=NEW.id)
        THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits per double-entry accounting')
        END;
    END;

    """)
    # Migrations via ALTER TABLE (idempotent, IF NOT EXISTS style checks)
    _ensure_schema(db)
    # Ensure indexes for existing DBs (IF NOT EXISTS handles)
    _ensure_indexes(db)
    db.commit()

def _ensure_dedup_index(db: DbHandle):
    """Enforce one-txn-per-account on old files (fresh files get inline UNIQUE).

    The fingerprint index was created non-unique, so DROP + UNIQUE replaces it
    on sqlite and pg. Fails loud-but-safe when dupes exist: enforcement stays
    off, data untouched.
    """
    for sql in [
        "DROP INDEX IF EXISTS idx_transactions_tenant_account_fingerprint;",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_tenant_account_fingerprint"
        " ON transactions(tenant_id, account_number, fingerprint_sha256);",
    ]:
        try:
            db.execute(sql)
        except Exception as e:
            print(
                "WARN: dedup unique-index migration failed"
                f" ({e}); find dupes via GROUP BY tenant_id, account_number,"
                " fingerprint_sha256 HAVING COUNT(*)>1"
            )


def _doc_index_cols(db, index_name):
    rows = db.execute(f"PRAGMA index_info({index_name})").fetchall()
    return [(c["name"] if isinstance(c, dict) else c[2]) for c in rows]


def _doc_index_is_unique(ix):
    return (ix["unique"] if isinstance(ix, dict) else ix[2]) == 1


def _doc_pg_migrate(db):
    """Drop old global-unique constraint(s), add composite. Returns enforced bool."""
    try:
        cur = db.execute(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conrelid = 'source_documents'::regclass AND contype = 'u';"
        )
        for row in cur.fetchall():
            name = row["conname"] if isinstance(row, dict) else row[0]
            defi = row["pg_get_constraintdef"] if isinstance(row, dict) else row[1]
            if defi and "sha256" in defi and "tenant_id" not in defi:
                db.execute(f"ALTER TABLE source_documents DROP CONSTRAINT {name};")
        cur = db.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = 'source_documents_tenant_sha_key';"
        )
        if not cur.fetchone():
            db.execute(
                "ALTER TABLE source_documents ADD CONSTRAINT source_documents_tenant_sha_key"
                " UNIQUE (tenant_id, sha256);"
            )
        cur = db.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = 'source_documents_tenant_sha_key';"
        )
        return cur.fetchone() is not None
    except Exception as e:
        print(f"WARN: doc tenant-sha pg migration: {e}")
        return False


def _doc_sqlite_uniques(db):
    """(has_global_unique, has_composite_unique) or None on error."""
    try:
        idxs = db.execute("PRAGMA index_list(source_documents)").fetchall()
    except Exception:
        return None
    has_global = any(
        _doc_index_is_unique(ix)
        and (ix["origin"] if isinstance(ix, dict) else ix[3]) == "u"
        and _doc_index_cols(db, ix["name"] if isinstance(ix, dict) else ix[1]) == ["sha256"]
        for ix in idxs
    )
    has_composite = any(
        _doc_index_is_unique(ix)
        and _doc_index_cols(db, ix["name"] if isinstance(ix, dict) else ix[1]) == ["tenant_id", "sha256"]
        for ix in idxs
    )
    return (has_global, has_composite)


def _doc_sqlite_ensure_composite(db):
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_source_documents_tenant_sha_unique"
            " ON source_documents(tenant_id, sha256);"
        )
    except Exception as e:
        print(f"WARN: doc tenant-sha unique index: {e}")


def _doc_sqlite_viewdefs(db):
    """Saved (name, sql) of views referencing the table, or None on error."""
    try:
        views = db.execute(
            "SELECT name, sql FROM sqlite_master"
            " WHERE type = 'view' AND sql LIKE '%source_documents%';"
        ).fetchall()
    except Exception:
        return None
    return [
        (
            (v["name"] if isinstance(v, dict) else v[0]),
            (v["sql"] if isinstance(v, dict) else v[1]),
        )
        for v in views
    ]


def _doc_sqlite_backup(db):
    """VACUUM INTO backup path, or None (abort) when it cannot be taken."""
    try:
        dblist = db.execute("PRAGMA database_list;").fetchall()
        mainfile = next(
            (
                (r["file"] if isinstance(r, dict) else r[2])
                for r in dblist
                if (r["name"] if isinstance(r, dict) else r[1]) == "main"
            ),
            "",
        )
        if not mainfile or mainfile == ":memory:":
            return None
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = f"{mainfile}.pre-mig-{stamp}.bak"
        db.execute(f"VACUUM INTO '{backup.replace(chr(39), chr(39) * 2)}';")
        return backup
    except Exception as e:
        print(f"WARN: pre-migration backup failed, aborting rebuild: {e}")
        return None


def _doc_sqlite_build_ddl(db):
    """(create_table_ddl, copy_stmt) preserving every column, FK, default."""
    cols = db.execute("PRAGMA table_info(source_documents)").fetchall()
    coldefs = []
    for c in cols:
        nm = c["name"] if isinstance(c, dict) else c[1]
        typ = c["type"] if isinstance(c, dict) else c[2]
        nn = c["notnull"] if isinstance(c, dict) else c[3]
        dflt = c["dflt_value"] if isinstance(c, dict) else c[4]
        pk = c["pk"] if isinstance(c, dict) else c[5]
        parts = [nm, typ or "TEXT"]
        if pk:
            parts.append("PRIMARY KEY")
        elif nn:
            parts.append("NOT NULL")
        if dflt is not None:
            d = dflt
            if "(" in d and not (d.startswith("(") and d.endswith(")")):
                d = f"({d})"
            parts.append(f"DEFAULT {d}")
        coldefs.append(" ".join(parts))
    fks = db.execute("PRAGMA foreign_key_list(source_documents)").fetchall()
    for fk in fks:
        tbl = fk["table"] if isinstance(fk, dict) else fk[2]
        frm = fk["from"] if isinstance(fk, dict) else fk[3]
        to = fk["to"] if isinstance(fk, dict) else fk[4]
        coldefs.append(f"FOREIGN KEY ({frm}) REFERENCES {tbl}({to})")
    coldefs.append("UNIQUE(tenant_id, sha256)")
    names = ", ".join((c["name"] if isinstance(c, dict) else c[1]) for c in cols)
    ddl = "CREATE TABLE source_documents_new (%s);" % ", ".join(coldefs)
    insert_sel = f"INSERT INTO source_documents_new ({names}) SELECT {names} FROM source_documents;"
    return (ddl, insert_sel)


def _doc_sqlite_drop_views(db, viewdefs):
    for vname, _ in viewdefs:
        db.execute(f'DROP VIEW IF EXISTS "{vname}";')


def _doc_sqlite_create_views(db, viewdefs, only_missing):
    if only_missing:
        have = {
            (r["name"] if isinstance(r, dict) else r[0])
            for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'view';").fetchall()
        }
        viewdefs = [(n, s) for n, s in viewdefs if n not in have]
    for _, vsql in viewdefs:
        db.execute(vsql.rstrip(";") + ";")


def _doc_sqlite_restore(db, viewdefs, backup):
    """Best-effort restore after a failed rebuild. Returns restored bool."""
    try:
        tables = {
            (r["name"] if isinstance(r, dict) else r[0])
            for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table';").fetchall()
        }
        if "source_documents_new" in tables and "source_documents" not in tables:
            db.execute("ALTER TABLE source_documents_new RENAME TO source_documents;")
        elif "source_documents_new" in tables:
            db.execute("DROP TABLE source_documents_new;")
        _doc_sqlite_create_views(db, viewdefs, True)
        db.execute("PRAGMA foreign_keys=ON;")
        db.commit()
        return True
    except Exception as e2:
        print(f"WARN: restore failed: {e2}; pre-migration backup at {backup}")
        return False


def _doc_sqlite_rebuild(db, viewdefs, backup):
    """View-safe table rebuild. Returns True only when fully complete."""
    try:
        ddl, insert_sel = _doc_sqlite_build_ddl(db)
        _doc_sqlite_drop_views(db, viewdefs)
        db.execute("PRAGMA foreign_keys=OFF;")
        db.execute(ddl)
        db.execute(insert_sel)
        db.execute("DROP TABLE source_documents;")
        db.execute("ALTER TABLE source_documents_new RENAME TO source_documents;")
        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_source_documents_tenant_sha ON source_documents(tenant_id, sha256);",
            "CREATE INDEX IF NOT EXISTS idx_source_documents_uploaded_by ON source_documents(uploaded_by);",
            "CREATE INDEX IF NOT EXISTS idx_source_documents_account ON source_documents(account_id);",
            "CREATE INDEX IF NOT EXISTS idx_source_documents_account_number ON source_documents(account_number);",
        ]:
            db.execute(sql)
        _doc_sqlite_create_views(db, viewdefs, False)
        db.execute("PRAGMA foreign_keys=ON;")
        db.commit()
        return True
    except Exception as e:
        print(f"WARN: doc table rebuild failed: {e}; attempting restore (backup at {backup})")
        return _doc_sqlite_restore(db, viewdefs, backup)


def _ensure_doc_tenant_sha_unique(db: DbHandle):
    """Per-tenant dedup: UNIQUE(tenant_id, sha256) replaces global UNIQUE(sha256).

    Fresh files get it inline. Old files: pg drops the old unique constraint(s)
    and adds the composite; sqlite rebuilds the table (constraints cannot be
    dropped there). Global-unique old data can never violate the composite,
    so the copy is safe.
    Rebuild safety: dependent views are saved + dropped first (SQLite refuses
    DROP+RENAME while a view references the name), a VACUUM INTO backup is
    taken first, and failure restores table + views from the surviving copy.
    Fails loud-but-safe: data untouched, WARN printed.
    """
    if db.backend == "pg":
        return _doc_pg_migrate(db)
    state = _doc_sqlite_uniques(db)
    if state is None:
        return False
    has_global, has_composite = state
    if not has_global:
        if not has_composite:
            _doc_sqlite_ensure_composite(db)
        return True
    viewdefs = _doc_sqlite_viewdefs(db)
    if viewdefs is None:
        return False
    backup = _doc_sqlite_backup(db)
    if backup is None:
        return False
    return _doc_sqlite_rebuild(db, viewdefs, backup)


def _ensure_span_dims(db: DbHandle):
    """Add page_width/page_height to old source_spans tables (Day-6 drill).

    Fresh files get the columns inline. sqlite has no ADD COLUMN IF NOT
    EXISTS, so duplicate-column errors are swallowed; pg uses IF NOT EXISTS.
    """
    for col in ("page_width", "page_height"):
        if db.backend == "pg":
            sql = f"ALTER TABLE source_spans ADD COLUMN IF NOT EXISTS {col} REAL;"
        else:
            sql = f"ALTER TABLE source_spans ADD COLUMN {col} REAL;"
        try:
            db.execute(sql)
        except Exception:
            pass


def _ensure_indexes(db: DbHandle):
    # Indexes for performance per homework Done Means: 1000 tx analyze <5s without LLM, <15s with LLM, PowerBI export
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_transactions_tenant_date ON transactions(tenant_id, txn_date);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(fingerprint_sha256);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_document ON transactions(document_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_account_number ON transactions(account_number);",
        "CREATE INDEX IF NOT EXISTS idx_source_documents_tenant_sha ON source_documents(tenant_id, sha256);",
        "CREATE INDEX IF NOT EXISTS idx_source_documents_uploaded_by ON source_documents(uploaded_by);",
        "CREATE INDEX IF NOT EXISTS idx_source_documents_account ON source_documents(account_id);",
        "CREATE INDEX IF NOT EXISTS idx_source_documents_account_number ON source_documents(account_number);",
        "CREATE INDEX IF NOT EXISTS idx_source_spans_tenant_doc ON source_spans(tenant_id, document_id);",
        "CREATE INDEX IF NOT EXISTS idx_source_spans_run ON source_spans(run_id);",
        "CREATE INDEX IF NOT EXISTS idx_classifications_tenant_txn ON classifications(tenant_id, transaction_id);",
        "CREATE INDEX IF NOT EXISTS idx_classifications_category ON classifications(category_id);",
        "CREATE INDEX IF NOT EXISTS idx_journal_entries_tenant_date ON journal_entries(tenant_id, entry_date);",
        "CREATE INDEX IF NOT EXISTS idx_journal_lines_entry ON journal_lines(entry_id);",
        "CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_id);",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_object ON audit_log(tenant_id, object_type, object_id);",
        "CREATE INDEX IF NOT EXISTS idx_flags_tenant_test ON flags(tenant_id, test_id);",
        "CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_kind ON usage_events(tenant_id, kind);",
        "CREATE INDEX IF NOT EXISTS idx_document_pages_doc ON document_pages(document_id);",
        "CREATE INDEX IF NOT EXISTS idx_extraction_runs_doc ON extraction_runs(document_id);",
        "CREATE INDEX IF NOT EXISTS idx_transaction_sources_txn ON transaction_sources(transaction_id);",
        "CREATE INDEX IF NOT EXISTS idx_transaction_sources_span ON transaction_sources(span_id);",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_tenant_account_number ON accounts(tenant_id, account_number) WHERE account_number IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_accounts_account_number ON accounts(account_number);",
        "CREATE INDEX IF NOT EXISTS idx_merchant_memory_tenant_merchant ON merchant_memory(tenant_id, normalized_merchant);",
        "CREATE INDEX IF NOT EXISTS idx_merchant_memory_account ON merchant_memory(account_number);",
        "CREATE INDEX IF NOT EXISTS idx_vendor_rules_tenant_merchant_account ON vendor_rules(tenant_id, normalized_merchant, account_number);",
    ]
    for sql in indexes:
        try:
            db.execute(sql)
        except Exception:
            pass

    _ensure_dedup_index(db)
    _ensure_doc_tenant_sha_unique(db)
    _ensure_span_dims(db)

    # Views for PowerBI star-schema per homework Part 5.10 - need to drop and recreate to include account_number per user per merchant per account enhancement
    # Drop existing views if old definition without account_number
    drop_views = [
        "DROP VIEW IF EXISTS fact_transactions;",
        "DROP VIEW IF EXISTS fact_journal;",
        "DROP VIEW IF EXISTS dim_account;",
        "DROP VIEW IF EXISTS dim_category;",
        "DROP VIEW IF NOT EXISTS dim_entity;",
        "DROP VIEW IF EXISTS dim_document;",
        "DROP VIEW IF EXISTS dim_date;",
    ]
    # SQLite doesn't support DROP VIEW IF NOT EXISTS for dim_entity typo above, handle separately
    for drop_sql in drop_views:
        try:
            # Handle typo for dim_entity
            if "NOT EXISTS" in drop_sql and "dim_entity" in drop_sql:
                db.execute("DROP VIEW IF EXISTS dim_entity;")
            else:
                db.execute(drop_sql.replace("IF NOT EXISTS","IF EXISTS").replace("IF NOT EXISTS","").strip() if "DROP" in drop_sql else drop_sql)
        except Exception:
            pass
    # Actually drop all views unconditionally to ensure new definition with account_number
    for view_name in ["fact_transactions","fact_journal","dim_account","dim_category","dim_entity","dim_document","dim_date"]:
        try:
            db.execute(f"DROP VIEW IF EXISTS {view_name};")
        except:
            pass

    views = [
        """CREATE VIEW fact_transactions AS
            SELECT t.id, t.tenant_id, t.entity_id, t.account_id, t.account_number, t.document_id, t.run_id, t.txn_date as date, t.description_raw, t.amount_minor, t.currency, t.direction, t.balance_after_minor, t.fingerprint_sha256, t.status, c.nature, c.business_pct, c.category_id, c.rationale, c.confidence
            FROM transactions t LEFT JOIN classifications c ON t.id = c.transaction_id;""",
        """CREATE VIEW IF NOT EXISTS fact_journal AS
            SELECT je.id as entry_id, je.tenant_id, je.entity_id, je.entry_date as date, je.memo, je.transaction_id, je.classification_id, jl.id as line_id, jl.account_id, jl.debit_minor, jl.credit_minor, a.code as account_code, a.name as account_name, a.type as account_type
            FROM journal_entries je JOIN journal_lines jl ON je.id = jl.entry_id LEFT JOIN accounts a ON jl.account_id = a.id;""",
        """CREATE VIEW IF NOT EXISTS dim_account AS
            SELECT id, tenant_id, entity_id, code, name, type FROM accounts;""",
        """CREATE VIEW IF NOT EXISTS dim_category AS
            SELECT DISTINCT category_id as id, category_id as name FROM classifications WHERE category_id IS NOT NULL
            UNION SELECT DISTINCT '6000' as id, 'Marketing' as name UNION SELECT '6100','Rent' UNION SELECT '6200','Fuel' UNION SELECT '6600','Bank Charges' UNION SELECT '7000','Drawings';""",
        """CREATE VIEW IF NOT EXISTS dim_entity AS
            SELECT id, name, plan_code, status FROM tenants
            UNION SELECT entity_id as id, entity_id as name, '' as plan_code, 'active' as status FROM (SELECT DISTINCT entity_id as entity_id FROM transactions WHERE entity_id IS NOT NULL) AS sub;""",
        """CREATE VIEW IF NOT EXISTS dim_document AS
            SELECT id, tenant_id, sha256, original_filename, size_bytes, mime, uploaded_at_utc, status, legal_hold FROM source_documents;""",
        """CREATE VIEW IF NOT EXISTS dim_date AS
            SELECT DISTINCT txn_date as date,
                   CAST(strftime('%Y', txn_date) AS INTEGER) as year,
                   CAST(strftime('%m', txn_date) AS INTEGER) as month,
                   CAST(strftime('%d', txn_date) AS INTEGER) as day,
                   CAST((strftime('%m', txn_date)+2)/3 AS INTEGER) as quarter,
                   CASE CAST(strftime('%m', txn_date) AS INTEGER)
                     WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March' WHEN 4 THEN 'April'
                     WHEN 5 THEN 'May' WHEN 6 THEN 'June' WHEN 7 THEN 'July' WHEN 8 THEN 'August'
                     WHEN 9 THEN 'September' WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December'
                   END as month_name,
                   CAST(strftime('%w', txn_date) AS INTEGER) as day_of_week,
                   CASE WHEN CAST(strftime('%w', txn_date) AS INTEGER) IN (0,6) THEN 1 ELSE 0 END as is_weekend
            FROM transactions
            UNION
            SELECT DISTINCT entry_date as date,
                   CAST(strftime('%Y', entry_date) AS INTEGER) as year,
                   CAST(strftime('%m', entry_date) AS INTEGER) as month,
                   CAST(strftime('%d', entry_date) AS INTEGER) as day,
                   CAST((strftime('%m', entry_date)+2)/3 AS INTEGER) as quarter,
                   CASE CAST(strftime('%m', entry_date) AS INTEGER)
                     WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March' WHEN 4 THEN 'April'
                     WHEN 5 THEN 'May' WHEN 6 THEN 'June' WHEN 7 THEN 'July' WHEN 8 THEN 'August'
                     WHEN 9 THEN 'September' WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December'
                   END as month_name,
                   CAST(strftime('%w', entry_date) AS INTEGER) as day_of_week,
                   CASE WHEN CAST(strftime('%w', entry_date) AS INTEGER) IN (0,6) THEN 1 ELSE 0 END as is_weekend
            FROM journal_entries WHERE entry_date IS NOT NULL;""",
    ]
    for sql in views:
        try:
            db.execute(sql)
        except Exception:
            pass

    # Triggers for journal balance constraint per AGENTS.md ledger-core double-entry
    # Day4: enforce on POSTED entries (see schema block above). SQLite syntax; on pg these
    # statements fail and are skipped - pg relies on app-level post_transaction validation.
    triggers = [
        "DROP TRIGGER IF EXISTS trg_journal_balance_check_insert;",
        "DROP TRIGGER IF EXISTS trg_journal_balance_check_update;",
        "DROP TRIGGER IF EXISTS trg_journal_balance_check_delete;",
        """CREATE TRIGGER IF NOT EXISTS trg_journal_lines_guard_insert
        AFTER INSERT ON journal_lines
        FOR EACH ROW
        WHEN (SELECT posted FROM journal_entries WHERE id=NEW.entry_id) = 1
        BEGIN
            SELECT CASE WHEN (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT COALESCE(SUM(credit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id)
            THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits (posted entry)')
            END;
        END;""",
        """CREATE TRIGGER IF NOT EXISTS trg_journal_lines_guard_update
        AFTER UPDATE ON journal_lines
        FOR EACH ROW
        WHEN (SELECT posted FROM journal_entries WHERE id=NEW.entry_id) = 1
        BEGIN
            SELECT CASE WHEN (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT COALESCE(SUM(credit_minor),0) FROM journal_lines WHERE entry_id=NEW.entry_id)
            THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits (posted entry)')
            END;
        END;""",
        """CREATE TRIGGER IF NOT EXISTS trg_journal_lines_guard_delete
        AFTER DELETE ON journal_lines
        FOR EACH ROW
        WHEN (SELECT posted FROM journal_entries WHERE id=OLD.entry_id) = 1
        BEGIN
            SELECT CASE WHEN (SELECT COUNT(*) FROM journal_lines WHERE entry_id=OLD.entry_id) > 0
            THEN RAISE(ABORT, 'Journal entry not balanced after delete: cannot remove lines from a posted entry (unpost first)')
            END;
        END;""",
        """CREATE TRIGGER IF NOT EXISTS trg_journal_entry_post
        AFTER UPDATE OF posted ON journal_entries
        FOR EACH ROW
        WHEN NEW.posted = 1
        BEGIN
            SELECT CASE WHEN (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.id) < 2
            THEN RAISE(ABORT, 'Journal entry not balanced: need at least 2 lines to post')
            END;
            SELECT CASE WHEN (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines WHERE entry_id=NEW.id) != (SELECT COALESCE(SUM(credit_minor),0) FROM journal_lines WHERE entry_id=NEW.id)
            THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits per double-entry accounting')
            END;
        END;""",
    ]
    for sql in triggers:
        try:
            db.execute(sql)
        except Exception:
            pass


def _cleanup_journals(db: DbHandle, tenant_id: str):
    """Unpost + delete journal lines/entries for tenant (delete guard blocks posted lines)."""
    try:
        db.execute(
            "UPDATE journal_entries SET posted=0 WHERE tenant_id=?", (tenant_id,)
        )
    except Exception:
        pass
    try:
        db.execute(
            "DELETE FROM journal_lines WHERE entry_id IN (SELECT id FROM journal_entries WHERE tenant_id=?)",
            (tenant_id,),
        )
    except Exception:
        pass
    try:
        db.execute("DELETE FROM journal_entries WHERE tenant_id=?", (tenant_id,))
    except Exception:
        pass


def cleanup_tenant(tenant_id: str):
    """Delete tenant data in FK-safe order: children first, parents last.
    Order: transaction_sources, classifications, transaction_revisions, flag_links, flags,
    journal_lines, journal_entries, transactions, merchant_memory, vendor_rules,
    source_spans, extraction_runs, document_pages, source_documents, accounts, audit_log,
    usage_events, subscriptions, users, reset_tokens via users, tenants last.
    Used by tests to avoid FOREIGN KEY constraint failed.
    """
    db = get_db()
    # Children of transactions
    try:
        db.execute("DELETE FROM transaction_sources WHERE transaction_id IN (SELECT id FROM transactions WHERE tenant_id=?)", (tenant_id,))
    except Exception:
        pass
    for tbl in ["classifications", "transaction_revisions"]:
        try:
            db.execute(f"DELETE FROM {tbl} WHERE tenant_id=?", (tenant_id,))
        except Exception:
            pass
    try:
        db.execute("DELETE FROM flag_links WHERE transaction_id IN (SELECT id FROM transactions WHERE tenant_id=?)", (tenant_id,))
    except Exception:
        pass
    try:
        db.execute("DELETE FROM flags WHERE tenant_id=?", (tenant_id,))
    except Exception:
        pass
    # Journals: lines reference entries and accounts, entries reference tenant
    _cleanup_journals(db, tenant_id)
    for tbl in ["transactions", "merchant_memory", "vendor_rules", "source_spans"]:
        try:
            db.execute(f"DELETE FROM {tbl} WHERE tenant_id=?", (tenant_id,))
        except Exception:
            pass
    try:
        db.execute("DELETE FROM extraction_runs WHERE document_id IN (SELECT id FROM source_documents WHERE tenant_id=?)", (tenant_id,))
    except Exception:
        pass
    try:
        db.execute("DELETE FROM document_pages WHERE document_id IN (SELECT id FROM source_documents WHERE tenant_id=?)", (tenant_id,))
    except Exception:
        pass
    try:
        db.execute("DELETE FROM source_documents WHERE tenant_id=?", (tenant_id,))
    except Exception:
        pass
    try:
        db.execute("DELETE FROM accounts WHERE tenant_id=?", (tenant_id,))
    except Exception:
        pass
    for tbl in ["audit_log", "usage_events", "subscriptions"]:
        try:
            db.execute(f"DELETE FROM {tbl} WHERE tenant_id=?", (tenant_id,))
        except Exception:
            pass
    # Users + reset_tokens
    try:
        cur = db.execute("SELECT id FROM users WHERE tenant_id=?", (tenant_id,))
        uids = [r["id"] if isinstance(r, dict) else r[0] for r in cur.fetchall()]
        for uid in uids:
            try:
                db.execute("DELETE FROM reset_tokens WHERE user_id=?", (uid,))
            except Exception:
                pass
        db.execute("DELETE FROM users WHERE tenant_id=?", (tenant_id,))
    except Exception:
        pass
    try:
        db.execute("DELETE FROM tenants WHERE id=?", (tenant_id,))
    except Exception:
        pass
    db.commit()

def _ensure_schema(db: DbHandle):
    # Paystack cols added via ALTER TABLE
    # Plus account_number per bank account per user question: each account number should have its own ledger (not own DB, but own account row + unique constraint per tenant)
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
        ("accounts", "account_number", "TEXT"),
        ("accounts", "bank_name", "TEXT"),
        ("accounts", "branch_code", "TEXT"),
        ("accounts", "is_active", "INTEGER DEFAULT 1"),
        ("accounts", "template", "TEXT DEFAULT 'personal'"),
        ("tenants", "active_template", "TEXT DEFAULT 'personal'"),
        ("source_documents", "account_id", "TEXT"),
        ("source_documents", "account_number", "TEXT"),
        ("source_documents", "bank_name", "TEXT"),
        ("source_documents", "branch_code", "TEXT"),
        ("transactions", "account_id", "TEXT"),
        ("transactions", "account_number", "TEXT"),
        ("journal_entries", "posted", "INTEGER DEFAULT 0"),
    ]
    for table, col, typ in cols_to_add:
        try:
            if db.backend == "pg":
                db.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}")
            else:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except Exception:
            pass  # column exists
    # Composite PK for the txn<->span link table: ON CONFLICT
    # (transaction_id, span_id) needs the matching constraint on pg.
    try:
        if db.backend == "pg":
            db.execute(
                "ALTER TABLE transaction_sources"
                " ADD PRIMARY KEY (transaction_id, span_id)"
            )
    except Exception:
        pass  # already exists

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
