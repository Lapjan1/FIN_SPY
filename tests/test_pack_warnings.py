"""Pack guardrails: multi-account tenants get an explicit manifest
warning so a whole-tenant ZIP is never handed over unthinkingly."""

import json
import uuid
import zipfile

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.reports import generate_evidence_pack, build_popia_zip


def _seed(tenant, accts):
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    for acct in accts:
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256,"
            " size_bytes, storage_key, status, original_filename,"
            " account_number) VALUES (?,?,?,?,?,?,?,?)",
            (f"doc-{tenant}-{acct}", tenant, f"sha-{tenant}-{acct}",
             10, f"missing-{acct}", "proposed", f"{acct}.pdf", acct),
        )
    db.commit()


def test_multi_account_warning_present():
    init_db()
    tenant = f"warn-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant, ["111", "222", "333"])
        pack = generate_evidence_pack(tenant)
        assert pack["manifest"]["warnings"], "3 accounts must warn"
        zp = build_popia_zip(tenant)
        with zipfile.ZipFile(zp) as zf:
            m = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert m["warnings"], "3 accounts must warn"
        assert "3" in m["warnings"][0]
    finally:
        cleanup_tenant(tenant)


def test_single_account_no_warning():
    init_db()
    tenant = f"warn-{uuid.uuid4().hex[:6]}"
    try:
        _seed(tenant, ["111"])
        pack = generate_evidence_pack(tenant)
        assert pack["manifest"]["warnings"] == []
    finally:
        cleanup_tenant(tenant)
