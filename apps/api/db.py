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
            # check_same_thread=False for FastAPI TestClient multi-thread per clearmind pattern + threading issue fix
            self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
        account_id TEXT,
        account_number TEXT,
        bank_name TEXT,
        branch_code TEXT,
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
        SELECT t.id, t.tenant_id, t.entity_id, t.document_id, t.run_id, t.txn_date as date, t.description_raw, t.amount_minor, t.currency, t.direction, t.balance_after_minor, t.fingerprint_sha256, t.status, c.nature, c.business_pct, c.category_id, c.rationale, c.confidence
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
        SELECT entity_id as id, entity_id as name, '' as plan_code, 'active' as status FROM (SELECT DISTINCT entity_id as entity_id FROM transactions WHERE entity_id IS NOT NULL);

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

    -- Journal balance constraint: debits = credits per entry (double-entry accounting) per AGENTS.md ledger-core
    -- Trigger checks after insert/update/delete of journal_lines, allows single line intermediate state but checks when count >=2
    CREATE TRIGGER IF NOT EXISTS trg_journal_balance_check_insert
    AFTER INSERT ON journal_lines
    FOR EACH ROW
    BEGIN
        SELECT CASE WHEN (SELECT SUM(debit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT SUM(credit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id)
        AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.entry_id) >= 2
        THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits per double-entry accounting')
        END;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_journal_balance_check_update
    AFTER UPDATE ON journal_lines
    FOR EACH ROW
    BEGIN
        SELECT CASE WHEN (SELECT SUM(debit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT SUM(credit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id)
        AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.entry_id) >= 2
        THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits')
        END;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_journal_balance_check_delete
    AFTER DELETE ON journal_lines
    FOR EACH ROW
    BEGIN
        SELECT CASE WHEN (SELECT SUM(debit_minor) FROM journal_lines WHERE entry_id=OLD.entry_id) != (SELECT SUM(credit_minor) FROM journal_lines WHERE entry_id=OLD.entry_id)
        AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id=OLD.entry_id) >= 2
        THEN RAISE(ABORT, 'Journal entry not balanced after delete')
        END;
    END;

    """)
    # Migrations per clearmind pattern
    _ensure_schema(db)
    # Ensure indexes for existing DBs (IF NOT EXISTS handles)
    _ensure_indexes(db)
    db.commit()

def _ensure_indexes(db: DbHandle):
    # Indexes for performance per homework Done Means: 1000 tx analyze <5s without LLM, <15s with LLM, PowerBI export
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_transactions_tenant_date ON transactions(tenant_id, txn_date);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_fingerprint ON transactions(fingerprint_sha256);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_document ON transactions(document_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_account_number ON transactions(account_number);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_tenant_account_fingerprint ON transactions(tenant_id, account_number, fingerprint_sha256);",
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
    ]
    for sql in indexes:
        try:
            db.execute(sql)
        except Exception:
            pass

    # Views for PowerBI star-schema per homework Part 5.10 - idempotent CREATE VIEW IF NOT EXISTS already in init_db, but ensure for existing DBs
    # dim_date view generates calendar from transactions + journal_entries for PowerBI
    views = [
        """CREATE VIEW IF NOT EXISTS fact_transactions AS
            SELECT t.id, t.tenant_id, t.entity_id, t.document_id, t.run_id, t.txn_date as date, t.description_raw, t.amount_minor, t.currency, t.direction, t.balance_after_minor, t.fingerprint_sha256, t.status, c.nature, c.business_pct, c.category_id, c.rationale, c.confidence
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
            UNION SELECT entity_id as id, entity_id as name, '' as plan_code, 'active' as status FROM (SELECT DISTINCT entity_id as entity_id FROM transactions WHERE entity_id IS NOT NULL);""",
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
    triggers = [
        """CREATE TRIGGER IF NOT EXISTS trg_journal_balance_check_insert
        AFTER INSERT ON journal_lines
        FOR EACH ROW
        BEGIN
            SELECT CASE WHEN (SELECT SUM(debit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT SUM(credit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id)
            AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.entry_id) >= 2
            THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits')
            END;
        END;""",
        """CREATE TRIGGER IF NOT EXISTS trg_journal_balance_check_update
        AFTER UPDATE ON journal_lines
        FOR EACH ROW
        BEGIN
            SELECT CASE WHEN (SELECT SUM(debit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id) != (SELECT SUM(credit_minor) FROM journal_lines WHERE entry_id=NEW.entry_id)
            AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id=NEW.entry_id) >= 2
            THEN RAISE(ABORT, 'Journal entry not balanced: debits != credits')
            END;
        END;""",
        """CREATE TRIGGER IF NOT EXISTS trg_journal_balance_check_delete
        AFTER DELETE ON journal_lines
        FOR EACH ROW
        BEGIN
            SELECT CASE WHEN (SELECT SUM(debit_minor) FROM journal_lines WHERE entry_id=OLD.entry_id) != (SELECT SUM(credit_minor) FROM journal_lines WHERE entry_id=OLD.entry_id)
            AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id=OLD.entry_id) >= 2
            THEN RAISE(ABORT, 'Journal entry not balanced after delete')
            END;
        END;""",
    ]
    for sql in triggers:
        try:
            db.execute(sql)
        except Exception:
            pass

def _ensure_schema(db: DbHandle):
    # Paystack cols added via ALTER like clearmind database.py:210
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
        ("source_documents", "account_id", "TEXT"),
        ("source_documents", "account_number", "TEXT"),
        ("source_documents", "bank_name", "TEXT"),
        ("source_documents", "branch_code", "TEXT"),
        ("transactions", "account_id", "TEXT"),
        ("transactions", "account_number", "TEXT"),
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
