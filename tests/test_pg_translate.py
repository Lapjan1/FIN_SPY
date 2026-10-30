"""pg _translate() must emit Postgres-valid DDL without needing a live server.

Root cause of the Oct28 Railway crash: sqlite-only strftime() /
CREATE VIEW IF NOT EXISTS / CREATE TRIGGER reached psycopg2 and killed boot
(IndexError at startup). These tests pin the translation layer.
"""
from apps.api.db import DbHandle


def _pg() -> DbHandle:
    db = DbHandle()
    db.backend = "pg"  # _translate is pure; no connection is touched
    return db


def test_translate_placeholders():
    out = _pg()._translate("SELECT * FROM t WHERE a=? AND b=?")
    assert out == "SELECT * FROM t WHERE a=%s AND b=%s"


def test_translate_no_strftime_left():
    src = (
        "SELECT CAST(strftime('%Y', txn_date) AS INTEGER) as year,"
        " CAST(strftime('%m', txn_date) AS INTEGER) as month,"
        " CAST(strftime('%d', txn_date) AS INTEGER) as day,"
        " CAST((strftime('%m', txn_date)+2)/3 AS INTEGER) as quarter,"
        " CAST(strftime('%w', txn_date) AS INTEGER) as dow FROM transactions"
    )
    out = _pg()._translate(src)
    assert "strftime" not in out
    assert "%" not in out  # no stray % escapes for psycopg2
    assert "EXTRACT(YEAR FROM txn_date::date)::INTEGER" in out
    assert "EXTRACT(MONTH FROM txn_date::date)::INTEGER" in out
    assert "EXTRACT(DAY FROM txn_date::date)::INTEGER" in out
    assert "EXTRACT(QUARTER FROM txn_date::date)::INTEGER" in out
    assert "EXTRACT(DOW FROM txn_date::date)::INTEGER" in out


def test_translate_view_or_replace():
    out = _pg()._translate("CREATE VIEW IF NOT EXISTS dim_date AS SELECT 1")
    assert out == "CREATE OR REPLACE VIEW dim_date AS SELECT 1"


def test_translate_or_replace_first_col_pk():
    out = _pg()._translate(
        "INSERT OR REPLACE INTO transactions (id, tenant_id) VALUES (?,?)"
    )
    assert out == (
        "INSERT INTO transactions (id, tenant_id) VALUES (%s,%s)"
        " ON CONFLICT (id) DO UPDATE SET tenant_id=EXCLUDED.tenant_id"
    )


def test_translate_or_replace_composite_pk():
    # transaction_sources PRIMARY KEY (transaction_id, span_id): the old
    # first-col assumption emitted ON CONFLICT (transaction_id), which
    # Postgres rejects with 42P10 InvalidColumnReference - crashing persist
    # after the txn row committed (pg autocommit) and stranding partial rows.
    out = _pg()._translate(
        "INSERT OR REPLACE INTO transaction_sources"
        " (transaction_id, span_id, role) VALUES (?,?,?)"
    )
    assert out == (
        "INSERT INTO transaction_sources (transaction_id, span_id, role)"
        " VALUES (%s,%s,%s)"
        " ON CONFLICT (transaction_id, span_id) DO UPDATE"
        " SET span_id=EXCLUDED.span_id, role=EXCLUDED.role"
    )


def test_executescript_pg_skips_triggers(monkeypatch):
    ran = []
    db = _pg()
    monkeypatch.setattr(db, "execute", lambda sql, params=(): ran.append(sql))
    db.executescript(
        "CREATE TABLE t (id INTEGER PRIMARY KEY);\n"
        "-- sqlite-only trigger\n"
        "CREATE TRIGGER trg AFTER INSERT ON t BEGIN SELECT 1; END;\n"
        "CREATE VIEW IF NOT EXISTS v AS SELECT 1;\n"
    )
    joined = "\n".join(ran)
    assert "TRIGGER" not in joined
    assert "CREATE TABLE t" in joined


def test_executescript_pg_skips_trigger_bodies(monkeypatch):
    # The `;`-splitter chops multi-statement trigger bodies; continuation
    # chunks (no TRIGGER keyword) used to execute and WARN loudly at every
    # boot. Whole CREATE..END blocks must be skipped on pg.
    ran = []
    db = _pg()
    monkeypatch.setattr(db, "execute", lambda sql, params=(): ran.append(sql))
    db.executescript(
        "CREATE TABLE t (id INTEGER PRIMARY KEY);\n"
        "CREATE TRIGGER trg AFTER INSERT ON t\n"
        "BEGIN\n"
        "    SELECT CASE WHEN 1 != 1\n"
        "    THEN RAISE(ABORT, 'first');\n"
        "    END;\n"
        "    SELECT CASE WHEN 2 != 2\n"
        "    THEN RAISE(ABORT, 'second');\n"
        "    END;\n"
        "END;\n"
        "CREATE TABLE u (id INTEGER PRIMARY KEY);\n"
    )
    joined = "\n".join(ran)
    assert "TRIGGER" not in joined
    assert "RAISE" not in joined
    assert "SELECT CASE" not in joined
    assert "CREATE TABLE t" in joined
    assert "CREATE TABLE u" in joined


def test_executescript_pg_strips_comment_percent(monkeypatch):
    # Live prod bug: a `--` schema comment containing `%` (merchant_memory
    # header: "% allocation") reached psycopg2, which raised "tuple index
    # out of range" with empty params - so merchant_memory was never
    # created on Postgres and /v1/me/export 500'd with UndefinedTable.
    ran = []
    db = _pg()
    monkeypatch.setattr(db, "execute", lambda sql, params=(): ran.append(sql))
    db.executescript(
        "-- Merchant memory: vendor grouping and % allocation, what if like?\n"
        "CREATE TABLE merchant_memory (id TEXT PRIMARY KEY, tenant_id TEXT);\n"
    )
    assert len(ran) == 1
    assert "%" not in ran[0]
    assert "?" not in ran[0]
    assert "CREATE TABLE merchant_memory" in ran[0]


def test_translate_or_replace_flag_links_composite():
    # flag_links PRIMARY KEY (flag_id, transaction_id): first-col
    # target (flag_id) is not unique -> 42P10 on Postgres.
    out = _pg()._translate(
        "INSERT OR REPLACE INTO flag_links"
        " (flag_id, transaction_id) VALUES (?,?)"
    )
    assert out == (
        "INSERT INTO flag_links (flag_id, transaction_id)"
        " VALUES (%s,%s)"
        " ON CONFLICT (flag_id, transaction_id) DO UPDATE"
        " SET transaction_id=EXCLUDED.transaction_id"
    )
