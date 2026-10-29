# Rebuild safety: an old-schema file (global UNIQUE(sha256) + dependent view)
# migrates to composite UNIQUE(tenant_id, sha256) with byte-identical rows,
# views restored, and a backup file. Runs against a tmp file, never dev/prod.
import sqlite3

import apps.api.db as dbmod
from apps.api.db import DbHandle, _ensure_doc_tenant_sha_unique

OLD_DDL = """CREATE TABLE source_documents (
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
    account_id TEXT,
    account_number TEXT,
    bank_name TEXT,
    branch_code TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);"""

SEEDS = [
    ("seed00xxxxxxxxxx", "t-0", "a" * 64, "O'Brien & Sons.pdf", "needs_password"),
    ("seed01xxxxxxxxxx", "t-1", "b" * 64, None, "queued"),
    ("seed02xxxxxxxxxx", "t-2", "c" * 64, "x" * 200 + ".pdf", "exception"),
    ("seed03xxxxxxxxxx", "t-0", "d" * 64, "stmt (1).pdf", "proposed"),
]


def _old_db(path):
    if path.exists():
        path.unlink()
    c = sqlite3.connect(str(path))
    c.execute("CREATE TABLE tenants (id TEXT PRIMARY KEY, name TEXT);")
    for t in ("t-0", "t-1", "t-2"):
        c.execute("INSERT INTO tenants (id, name) VALUES (?, ?);", (t, t))
    c.execute(OLD_DDL)
    for sid, ten, sha, fn, st in SEEDS:
        c.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes,"
            " storage_key, original_filename, status) VALUES (?,?,?,?,?,?,?);",
            (sid, ten, sha, 4242, f"data/vault/{sha}.pdf", fn, st),
        )
    c.execute(
        "CREATE VIEW dim_document AS SELECT id, tenant_id, sha256,"
        " original_filename FROM source_documents;"
    )
    c.commit()
    c.close()


def test_rebuild_preserves_rows_views_and_adds_composite(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    target = tmp_path / "old.db"
    _old_db(target)
    monkeypatch.setattr(dbmod, "DB_PATH", target)
    db = DbHandle()
    before = sorted(
        db.execute("SELECT * FROM source_documents ORDER BY id;").fetchall(),
        key=lambda r: r["id"] if isinstance(r, dict) else r[0],
    )

    assert _ensure_doc_tenant_sha_unique(db) is True

    after = sorted(
        db.execute("SELECT * FROM source_documents ORDER BY id;").fetchall(),
        key=lambda r: r["id"] if isinstance(r, dict) else r[0],
    )
    norm = lambda rows: [tuple(r) if not isinstance(r, dict) else tuple(r.values()) for r in rows]  # noqa: E731
    assert norm(after) == norm(before)
    idxs = db.execute("PRAGMA index_list(source_documents);").fetchall()
    uniques = sorted(
        (ix["name"] if isinstance(ix, dict) else ix[1])
        for ix in idxs
        if (ix["unique"] if isinstance(ix, dict) else ix[2]) == 1
    )
    assert any("tenant_sha" in n or n.startswith("sqlite_autoindex") for n in uniques)
    cols = db.execute("PRAGMA index_info(sqlite_autoindex_source_documents_2);").fetchall()
    assert sorted(c["name"] if isinstance(c, dict) else c[2] for c in cols) == ["sha256", "tenant_id"]
    views = db.execute("SELECT name FROM sqlite_master WHERE type='view';").fetchall()
    assert "dim_document" in [v["name"] if isinstance(v, dict) else v[0] for v in views]
    assert db.execute("SELECT COUNT(*) c FROM dim_document;").fetchone()[0] == 4
    assert list(tmp_path.glob("old.db.pre-mig-*.bak"))
    # Cross-tenant same-sha insert now works.
    db.execute(
        "INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, status)"
        " VALUES (?,?,?,?,?,?);",
        ("x" * 16, "t-9", "a" * 64, 1, "k", "queued"),
    )
    db.commit()
    # Second run is a no-op that still reports enforced.
    assert _ensure_doc_tenant_sha_unique(db) is True
    assert db.execute("SELECT COUNT(*) c FROM source_documents;").fetchone()[0] == 5
