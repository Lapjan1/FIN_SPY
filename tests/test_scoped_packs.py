"""Account boundary: evidence-pack, POPIA export, and the signed summary
contain only the scoped account's rows and originals. Nothing leaves the
building except through an account scope."""

import csv
import json
import uuid
import zipfile
from pathlib import Path

from apps.api.classify import decide
from apps.api.db import init_db, get_db, cleanup_tenant, append_audit_log
from apps.api.ledger import post_transaction
from apps.api.reports import (generate_evidence_pack, build_popia_zip)
from apps.api.signing import build_report_pdf
from apps.worker.parsers.registry import seed_coa


def _seed(tenant):
    db = get_db()
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)",
               (tenant, "t"))
    seed_coa(tenant, template="personal", db=db)
    vaults = []
    for acct, bank, cat in (("111", "FNB", "6030"),
                            ("222", "ABSA", "6040")):
        db.execute(
            "INSERT INTO accounts (id, tenant_id, code, name, type,"
            " account_number, template) VALUES (?,?,?,?,?,?,?)",
            (f"bank-{tenant}-{acct}", tenant, "1000",
             f"{bank} {acct}", "asset", acct, "personal"),
        )
        sha = f"sha-{tenant}-{acct}"
        vault = Path(f"data/vault/{sha}.pdf")
        vault.parent.mkdir(parents=True, exist_ok=True)
        vault.write_bytes(f"%PDF-{acct}".encode())
        vaults.append(vault)
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256,"
            " size_bytes, storage_key, status, original_filename,"
            " account_number, bank_name) VALUES (?,?,?,?,?,?,?,?,?)",
            (f"doc-{tenant}-{acct}", tenant, sha, 10,
             str(vault), "proposed", f"{bank}.pdf", acct, bank),
        )
        txn_id = f"txn-{tenant}-{acct}"
        db.execute(
            "INSERT INTO transactions (id, tenant_id, account_id,"
            " account_number, document_id, txn_date, description_raw,"
            " amount_minor, direction, fingerprint_sha256, status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (txn_id, tenant, f"bank-{tenant}-{acct}", acct,
             f"doc-{tenant}-{acct}", "2026-10-10", f"{bank} SHOP",
             -5000, "debit", f"fp-{tenant}-{acct}", "proposed"),
        )
        db.execute(
            "INSERT INTO extraction_runs (id, document_id,"
            " status) VALUES (?,?,?)",
            (f"run-{tenant}-{acct}", f"doc-{tenant}-{acct}",
             "done"),
        )
        db.commit()
        cur = db.execute("SELECT * FROM transactions WHERE id=?",
                         (txn_id,))
        row = cur.fetchone()
        txn = dict(row) if not isinstance(row, dict) else row
        cls = decide(txn_id, "business", 100, cat, "seed", None,
                     "seed", tenant)
        post_transaction(txn, {"id": cls["id"], "category_id": cat,
                              "nature": "business", "business_pct": 100})
        append_audit_log(tenant, 1, "txn.seeded", "transactions",
                         txn_id, {"acct": acct})
    # Flag linked only to the 111 txn.
    db.execute(
        "INSERT INTO flags (id, tenant_id, test_id, result_json)"
        " VALUES (?,?,?,?)",
        (f"flag-{tenant}", tenant, "DUP", "{}"),
    )
    db.execute(
        "INSERT INTO flag_links (flag_id, transaction_id) VALUES (?,?)",
        (f"flag-{tenant}", f"txn-{tenant}-111"),
    )
    db.execute(
        "INSERT INTO merchant_memory (id, tenant_id, normalized_merchant,"
        " account_number, category_id) VALUES (?,?,?,?,?)",
        (f"mem-{tenant}-111", tenant, "shop", "111", "6030"),
    )
    db.execute(
        "INSERT INTO merchant_memory (id, tenant_id, normalized_merchant,"
        " account_number, category_id) VALUES (?,?,?,?,?)",
        (f"mem-{tenant}-222", tenant, "shop", "222", "6040"),
    )
    db.commit()
    return vaults


def _cleanup(tenant, vaults):
    for v in vaults:
        v.unlink(missing_ok=True)
    cleanup_tenant(tenant)


def _zip_csv(zip_path, name):
    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if n.endswith(name)]
        assert members, zf.namelist()
        with zf.open(members[0]) as f:
            return list(csv.DictReader(
                f.read().decode("utf-8").splitlines()))


def test_evidence_pack_scoped_to_account():
    init_db()
    tenant = f"scope-{uuid.uuid4().hex[:6]}"
    vaults = _seed(tenant)
    try:
        pack = generate_evidence_pack(tenant, account_number="111")
        assert pack["manifest"]["scope"] == {"account_number": "111"}
        originals = [f for f in pack["manifest"]["files"]
                     if f["role"] == "original"]
        assert len(originals) == 1
        assert f"sha-{tenant}-111" in originals[0]["path"]
        with zipfile.ZipFile(pack["file_key"]) as zf:
            audit = json.loads(zf.read("audit.json").decode("utf-8"))
        obj_ids = {a["object_id"] for a in audit}
        assert obj_ids == {f"txn-{tenant}-111"}, obj_ids
    finally:
        _cleanup(tenant, vaults)


def test_popia_export_scoped_to_account():
    init_db()
    tenant = f"scope-{uuid.uuid4().hex[:6]}"
    vaults = _seed(tenant)
    try:
        zp = build_popia_zip(tenant, account_number="111")
        with zipfile.ZipFile(zp) as zf:
            manifest = json.loads(
                zf.read("manifest.json").decode("utf-8"))
            assert manifest["scope"] == {"account_number": "111"}
            names = zf.namelist()
        assert [n for n in names if n.startswith("originals/")].__len__() == 1
        txns = _zip_csv(zp, "transactions.csv")
        assert len(txns) == 1
        assert txns[0]["account_number"] == "111"
        docs = _zip_csv(zp, "source_documents.csv")
        assert len(docs) == 1
        mem = _zip_csv(zp, "merchant_memory.csv")
        assert {m["account_number"] for m in mem} == {"111"}
        flags = _zip_csv(zp, "flags.csv")
        assert len(flags) == 1
    finally:
        _cleanup(tenant, vaults)


def test_signed_summary_scoped_to_account(tmp_path):
    init_db()
    tenant = f"scope-{uuid.uuid4().hex[:6]}"
    vaults = _seed(tenant)
    try:
        out = tmp_path / "scoped.pdf"
        info = build_report_pdf(tenant, "2026-01-01", "2026-12-31",
                                out, account_number="111")
        assert info["txn_count"] == 1, info
        assert info["scope"] == {"account_number": "111"}
    finally:
        _cleanup(tenant, vaults)


def test_packs_default_to_whole_tenant():
    init_db()
    tenant = f"scope-{uuid.uuid4().hex[:6]}"
    vaults = _seed(tenant)
    try:
        pack = generate_evidence_pack(tenant)
        assert pack["manifest"]["scope"] == {"account_number": None}
        originals = [f for f in pack["manifest"]["files"]
                     if f["role"] == "original"]
        assert len(originals) == 2
    finally:
        _cleanup(tenant, vaults)
