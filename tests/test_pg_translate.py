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
