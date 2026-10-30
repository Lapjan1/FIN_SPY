"""
Boot/log redaction: a full Postgres URL (with password) reached Railway
logs via worker boot print. DSNs must be masked everywhere they are
printed; diagnostics keep working, secrets never do.
"""

from apps.api.db import redact_url


def test_redact_postgres_url():
    out = redact_url("postgres://user:s3cret@host:5432/railway")
    assert "s3cret" not in out
    assert "user" not in out
    assert out == "postgres://***@host:5432/railway"


def test_redact_postgresql_scheme():
    out = redact_url("postgresql://a:b@h/db?sslmode=require")
    assert ":b@" not in out and "a:b" not in out
    assert out.startswith("postgresql://***@")


def test_redact_leaves_sqlite_and_plain_text():
    assert redact_url("sqlite:///./data/fin_spy.db") == "sqlite:///./data/fin_spy.db"
    assert redact_url("no url here") == "no url here"
    assert redact_url("") == ""
    assert redact_url(None) is None


def test_redact_inside_prose():
    msg = "connection to postgres://u:p@h:5432/d failed: timeout"
    out = redact_url(msg)
    assert "u:p@" not in out
    assert "timeout" in out
