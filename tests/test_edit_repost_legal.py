"""
Edit repost + forward re-verify + legal report + sha256 intact.

Rule: editing amount/date on a posted txn reverses + reposts its journals
(append-only, never delete); stored balances are immutable bank-printed source
facts, so forward effects = reposted journals (derived statements read live)
+ re-executed reconciliation checks; every human change is reported with
reasons; source hashes must verify intact afterwards.
"""

import hashlib
import uuid
from pathlib import Path

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.api.ledger import post_transaction, trial_balance
from apps.api.classify import decide


def _tenant(prefix="repost"):
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    init_db()
    db = get_db()
    db.execute(
        "INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}")
    )
    db.commit()
    return tenant


def _bank_account(tenant, acct_no="123456"):
    from apps.worker.parsers.registry import seed_coa

    seed_coa(tenant, template="personal")
    db = get_db()
    bank_id = f"bank-{tenant}-{acct_no}"
    db.execute(
        "INSERT INTO accounts (id, tenant_id, code, name, type, account_number, template)"
        " VALUES (?,?,?,?,?,?,?)",
        (bank_id, tenant, "1000", "Bank - Test", "asset", acct_no, "personal"),
    )
    db.commit()
    return bank_id


def _txn(
    tenant,
    bank_id,
    acct_no="123456",
    amount=-45000,
    direction="debit",
    desc="WOOLWORTHS CT",
    date="2026-10-10",
    balance_after=None,
    status="proposed",
    document_id=None,
    run_id=None,
):
    db = get_db()
    txn_id = f"txn-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO transactions (id, tenant_id, account_id, account_number, txn_date,"
        " description_raw, amount_minor, direction, balance_after_minor,"
        " fingerprint_sha256, status, document_id, run_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            txn_id,
            tenant,
            bank_id,
            acct_no,
            date,
            desc,
            amount,
            direction,
            balance_after,
            f"fp-{uuid.uuid4().hex[:8]}",
            status,
            document_id,
            run_id,
        ),
    )
    db.commit()
    cur = db.execute("SELECT * FROM transactions WHERE id=?", (txn_id,))
    row = cur.fetchone()
    return dict(row) if not isinstance(row, dict) else row


def _doc_with_run(tenant, opening=None, closing=None):
    db = get_db()
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    sha = f"sha-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO source_documents (id, tenant_id, sha256, original_filename,"
        " size_bytes, mime, status, storage_key) VALUES (?,?,?,?,?,?,?,?)",
        (
            doc_id,
            tenant,
            sha,
            "stmt.pdf",
            100,
            "application/pdf",
            "extracted",
            f"data/vault/{sha}.pdf",
        ),
    )
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO extraction_runs (id, document_id, pipeline_version, status,"
        " opening_balance_minor, closing_balance_minor) VALUES (?,?,?,?,?,?)",
        (run_id, doc_id, "v1", "done", opening, closing),
    )
    db.commit()
    return doc_id, run_id


def _span(tenant, run_id, doc_id, txn_id, line_id="L001", text="WOOLWORTHS 450.00"):
    db = get_db()
    span_id = f"sp-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO source_spans (id, tenant_id, run_id, document_id, page_no,"
        " line_id, bbox_x0, bbox_y0, bbox_x1, bbox_y1, text, text_sha256)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            span_id,
            tenant,
            run_id,
            doc_id,
            1,
            line_id,
            10,
            20,
            90,
            25,
            text,
            hashlib.sha256(text.encode()).hexdigest(),
        ),
    )
    db.execute(
        "INSERT INTO transaction_sources (transaction_id, span_id, role) VALUES (?,?,?)",
        (txn_id, span_id, "amount"),
    )
    db.commit()
    return span_id


def _api_user():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    init_db()
    tenant = f"repapi-{uuid.uuid4().hex[:6]}"
    email = f"rep_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234", "name": "T", "tenant_id": tenant},
    )
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}


def _entries_for(txn_id, tenant):
    db = get_db()
    cur = db.execute(
        "SELECT je.*, (SELECT COALESCE(SUM(debit_minor),0) FROM journal_lines"
        " WHERE entry_id=je.id) AS debits FROM journal_entries je"
        " WHERE je.transaction_id=? AND je.tenant_id=? ORDER BY je.created_at ASC",
        (txn_id, tenant),
    )
    return [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]


def test_amount_edit_reposts_and_trial_balances():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, amount=-45000)
        decide(txn["id"], "private", 0, "6020", "groceries", 1, "first", tenant)
        post_transaction(txn, {"category_id": "6020"})
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"amount_minor": -50000, "reason": "correct amount"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["repost"] is not None
        assert len(body["repost"]["reversed_entry_ids"]) == 1
        assert body["repost"]["fresh_category"] == "6020"
        entries = _entries_for(txn["id"], tenant)
        assert len(entries) == 3  # original + reversal + fresh, append-only
        assert entries[1]["memo"].startswith("Reversal of")
        assert entries[1]["debits"] == 45000  # mirror of original
        assert entries[2]["debits"] == 50000  # fresh at corrected amount
        tb = trial_balance(tenant)
        assert tb["balanced"] is True and tb["zero"] is True
        by_code = {ln["code"]: ln for ln in tb["lines"]}
        assert by_code["6020"]["debits"] - by_code["6020"]["credits"] == 50000
    finally:
        cleanup_tenant(tenant)


def test_date_edit_reposts_with_new_entry_date():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, date="2026-10-10")
        decide(txn["id"], "private", 0, "6020", "g", 1, "first", tenant)
        post_transaction(txn, {"category_id": "6020"})
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"txn_date": "2026-10-11", "reason": "correct date"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["repost"] is not None
        entries = _entries_for(txn["id"], tenant)
        assert len(entries) == 3
        assert entries[2]["entry_date"] == "2026-10-11"
    finally:
        cleanup_tenant(tenant)


def test_description_only_edit_posts_nothing():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, desc="CHECKERS 123")
        decide(txn["id"], "private", 0, "6020", "g", 1, "first", tenant)
        post_transaction(txn, {"category_id": "6020"})
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"description_raw": "CHECKERS 456", "reason": "typo"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["repost"] is None
        assert r.json()["reverification"] is None
        assert len(_entries_for(txn["id"], tenant)) == 1
    finally:
        cleanup_tenant(tenant)


def test_unposted_amount_edit_posts_nothing():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, amount=-45000)
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"amount_minor": -50000, "reason": "fix before post"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["repost"] is None
        assert len(_entries_for(txn["id"], tenant)) == 0
        # ...but the next post uses corrected values
        db = get_db()
        cur = db.execute(
            "SELECT amount_minor FROM transactions WHERE id=?", (txn["id"],)
        )
        row = cur.fetchone()
        assert (row["amount_minor"] if isinstance(row, dict) else row[0]) == -50000
    finally:
        cleanup_tenant(tenant)


def test_vendor_posted_edit_reposts_to_inferred_target():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, desc="WOOLWORTHS CT")
        # Vendor-style post with no classification row
        post_transaction(txn, {"category_id": "6020"})
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"amount_minor": -48000, "reason": "correct"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["repost"] is not None
        assert body["repost"]["target_inferred"] is True
        entries = _entries_for(txn["id"], tenant)
        assert len(entries) == 3
        tb = trial_balance(tenant)
        assert tb["balanced"] is True
    finally:
        cleanup_tenant(tenant)


def test_redecided_then_edited_reverses_everything():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, amount=-45000)
        decide(txn["id"], "unknown", 0, "9999", "parked", 1, "first", tenant)
        post_transaction(txn, {"category_id": "9999"})
        decide(txn["id"], "private", 0, "6020", "groceries", 1, "second", tenant)
        assert len(_entries_for(txn["id"], tenant)) == 2  # original + transfer
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"amount_minor": -50000, "reason": "correct amount"},
        )
        assert r.status_code == 200, r.text
        entries = _entries_for(txn["id"], tenant)
        assert len(entries) == 5  # orig + transfer + 2 reversals + fresh
        tb = trial_balance(tenant)
        assert tb["balanced"] is True and tb["zero"] is True
        by_code = {ln["code"]: ln for ln in tb["lines"]}
        assert by_code["6020"]["debits"] - by_code["6020"]["credits"] == 50000
        assert by_code["9999"]["debits"] - by_code["9999"]["credits"] == 0
    finally:
        cleanup_tenant(tenant)


def test_reverify_reports_forward_breaks_fixed():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        doc_id, run_id = _doc_with_run(tenant, opening=100000, closing=75000)
        # Bank-printed balances consistent with TRUE amounts; B stored wrong.
        _txn(
            tenant,
            bank_id,
            amount=-10000,
            desc="A",
            date="2026-10-01",
            balance_after=90000,
            document_id=doc_id,
            run_id=run_id,
        )
        txn_b = _txn(
            tenant,
            bank_id,
            amount=-200000,
            desc="B-WRONG",
            date="2026-10-02",
            balance_after=70000,
            document_id=doc_id,
            run_id=run_id,
        )
        _txn(
            tenant,
            bank_id,
            amount=5000,
            direction="credit",
            desc="C",
            date="2026-10-03",
            balance_after=75000,
            document_id=doc_id,
            run_id=run_id,
        )
        r = client.post(
            f"/v1/review-queue/{txn_b['id']}/edit",
            headers=h,
            json={
                "amount_minor": -20000,
                "description_raw": "B",
                "reason": "fix extraction error",
            },
        )
        assert r.status_code == 200, r.text
        reverify = r.json()["reverification"]
        assert reverify is not None
        assert reverify["rows_checked"] == 3
        assert reverify["overall_pass"] is True
        assert reverify["running_top_bottom"]["pass"] is True
        assert reverify["running_bottom_top"]["pass"] is True
        assert reverify["opening_closing"]["pass"] is True
        # Stored source balances untouched by the correction
        db = get_db()
        cur = db.execute(
            "SELECT balance_after_minor FROM transactions WHERE id=?", (txn_b["id"],)
        )
        row = cur.fetchone()
        assert (
            row["balance_after_minor"] if isinstance(row, dict) else row[0]
        ) == 70000
    finally:
        cleanup_tenant(tenant)


def test_reverify_flags_break_introduced():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        doc_id, run_id = _doc_with_run(tenant, opening=100000, closing=75000)
        _txn(
            tenant,
            bank_id,
            amount=-10000,
            desc="A",
            date="2026-10-01",
            balance_after=90000,
            document_id=doc_id,
            run_id=run_id,
        )
        txn_b = _txn(
            tenant,
            bank_id,
            amount=-20000,
            desc="B",
            date="2026-10-02",
            balance_after=70000,
            document_id=doc_id,
            run_id=run_id,
        )
        _txn(
            tenant,
            bank_id,
            amount=5000,
            direction="credit",
            desc="C",
            date="2026-10-03",
            balance_after=75000,
            document_id=doc_id,
            run_id=run_id,
        )
        r = client.post(
            f"/v1/review-queue/{txn_b['id']}/edit",
            headers=h,
            json={"amount_minor": -99999, "reason": "bad edit"},
        )
        assert r.status_code == 200, r.text
        reverify = r.json()["reverification"]
        assert reverify["overall_pass"] is False
        assert reverify["running_top_bottom"]["break_count"] >= 1
    finally:
        cleanup_tenant(tenant)


def test_source_hashes_intact_after_edit():
    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        doc_id, run_id = _doc_with_run(tenant, opening=100000, closing=90000)
        txn = _txn(
            tenant,
            bank_id,
            amount=-10000,
            balance_after=90000,
            document_id=doc_id,
            run_id=run_id,
        )
        span_id = _span(tenant, run_id, doc_id, txn["id"])
        db = get_db()
        decide(txn["id"], "private", 0, "6020", "g", 1, "first", tenant)
        post_transaction(txn, {"category_id": "6020"})

        def snapshot():
            out = {}
            for tbl, key in [
                ("source_documents", doc_id),
                ("extraction_runs", run_id),
                ("source_spans", span_id),
            ]:
                cur = db.execute(f"SELECT * FROM {tbl} WHERE id=?", (key,))
                row = cur.fetchone()
                d = dict(row) if not isinstance(row, dict) else row
                out[tbl] = hashlib.sha256(repr(sorted(d.items())).encode()).hexdigest()
            return out

        before = snapshot()
        old_fp = txn["fingerprint_sha256"]
        r = client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"amount_minor": -12000, "reason": "correct"},
        )
        assert r.status_code == 200, r.text
        assert snapshot() == before  # spans, run, document byte-identical
        # Fingerprint moved forward; old value preserved in revision
        cur = db.execute(
            "SELECT fingerprint_sha256 FROM transactions WHERE id=?", (txn["id"],)
        )
        row = cur.fetchone()
        new_fp = row["fingerprint_sha256"] if isinstance(row, dict) else row[0]
        assert new_fp != old_fp
        cur = db.execute(
            "SELECT old_value, new_value FROM transaction_revisions"
            " WHERE transaction_id=? AND field='amount_minor'",
            (txn["id"],),
        )
        row = cur.fetchone()
        d = dict(row) if not isinstance(row, dict) else row
        assert d["old_value"] == "-10000" and d["new_value"] == "-12000"
    finally:
        cleanup_tenant(tenant)


def test_human_changes_report_and_verify():
    from apps.api.audit import verify_integrity

    client, tenant, h = _api_user()
    vault_file = None
    try:
        bank_id = _bank_account(tenant)
        txn = _txn(tenant, bank_id, desc="CHECKERS 1")
        decide(txn["id"], "private", 0, "6020", "g", 1, "first", tenant)
        post_transaction(txn, {"category_id": "6020"})
        client.post(
            f"/v1/review-queue/{txn['id']}/edit",
            headers=h,
            json={"amount_minor": -48000, "reason": "till slip says 480"},
        )
        r = client.get("/v1/audit/human-changes", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["revision_count"] >= 1
        rev = [x for x in body["revisions"] if x["field"] == "amount_minor"][0]
        assert rev["old_value"] == "-45000" and rev["new_value"] == "-48000"
        assert rev["reason"] == "till slip says 480"
        assert "@test.com" in (rev["actor_email"] or "")
        actions = [a["action"] for a in body["journal_actions"]]
        assert "review.edit" in actions and "journal.repost" in actions
        assert "classify.decide" in actions
        # Filter by transaction
        r = client.get(f"/v1/audit/human-changes?transaction_id={txn['id']}", headers=h)
        assert r.json()["revision_count"] >= 1
        # Vault file present + chain intact
        content = b"%PDF-1.4 test vault bytes"
        sha = hashlib.sha256(content).hexdigest()
        db = get_db()
        db.execute(
            "INSERT INTO source_documents (id, tenant_id, sha256, original_filename,"
            " size_bytes, mime, status, storage_key) VALUES (?,?,?,?,?,?,?,?)",
            (
                f"doc-vault-{tenant[-6:]}",
                tenant,
                sha,
                "v.pdf",
                len(content),
                "application/pdf",
                "extracted",
                f"{sha}.pdf",
            ),
        )
        db.commit()
        vault_file = Path("data/vault") / f"{sha}.pdf"
        vault_file.parent.mkdir(parents=True, exist_ok=True)
        vault_file.write_bytes(content)
        assert verify_integrity(tenant)["intact"] is True
        r = client.get("/v1/audit/verify", headers=h)
        assert r.status_code == 200
        assert r.json()["intact"] is True
        assert r.json()["audit_chain"]["checked"] >= 1
        # Forged audit row is detected
        db.execute(
            "INSERT INTO audit_log (tenant_id, actor_id, action, object_type, object_id,"
            " payload_json, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?)",
            (
                tenant,
                1,
                "review.edit",
                "transactions",
                txn["id"],
                '{"forged":true}',
                "0" * 64,
                "f" * 64,
            ),
        )
        db.commit()
        assert verify_integrity(tenant)["intact"] is False
        assert verify_integrity(tenant)["audit_chain"]["ok"] is False
    finally:
        if vault_file is not None and vault_file.exists():
            vault_file.unlink()
        cleanup_tenant(tenant)


def test_human_changes_tenant_id_not_injected():
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    init_db()
    evil = "evil' OR '1'='1"
    email = f"evil_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "pass1234", "name": "T", "tenant_id": evil},
    )
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    h = {"X-User-Id": str(r.json()["id"])}
    try:
        r = client.get("/v1/audit/human-changes", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["revision_count"] == 0  # bound param: no leak, no crash
        r = client.get("/v1/audit/verify", headers=h)
        assert r.status_code == 200
        assert r.json()["intact"] is True
    finally:
        cleanup_tenant(evil)


def test_edit_rollback_on_fingerprint_collision():
    from apps.api.main import fingerprint_txn

    client, tenant, h = _api_user()
    try:
        bank_id = _bank_account(tenant)
        txn_a = _txn(tenant, bank_id, amount=-10000, desc="ALPHA", date="2026-10-01")
        txn_b = _txn(tenant, bank_id, amount=-20000, desc="BETA", date="2026-10-02")
        # B carries a real fingerprint so A's edit into it truly collides
        db = get_db()
        db.execute(
            "UPDATE transactions SET fingerprint_sha256=? WHERE id=?",
            (fingerprint_txn("2026-10-02", -20000, "BETA"), txn_b["id"]),
        )
        db.commit()
        decide(txn_a["id"], "private", 0, "6020", "g", 1, "first", tenant)
        post_transaction(txn_a, {"category_id": "6020"})
        db = get_db()
        cur = db.execute(
            "SELECT COUNT(*) c FROM transaction_revisions WHERE tenant_id=?", (tenant,)
        )
        row = cur.fetchone()
        revs_before = row["c"] if isinstance(row, dict) else row[0]
        # Edit A into an exact duplicate of B -> 422 + full rollback
        r = client.post(
            f"/v1/review-queue/{txn_a['id']}/edit",
            headers=h,
            json={
                "amount_minor": -20000,
                "description_raw": "BETA",
                "txn_date": "2026-10-02",
                "reason": "oops",
            },
        )
        assert r.status_code == 422
        assert "duplicate" in r.text.lower()
        cur = db.execute(
            "SELECT COUNT(*) c FROM transaction_revisions WHERE tenant_id=?", (tenant,)
        )
        row = cur.fetchone()
        assert (row["c"] if isinstance(row, dict) else row[0]) == revs_before
        assert len(_entries_for(txn_a["id"], tenant)) == 1  # no orphan reversal
        cur = db.execute(
            "SELECT amount_minor FROM transactions WHERE id=?", (txn_a["id"],)
        )
        row = cur.fetchone()
        assert (row["amount_minor"] if isinstance(row, dict) else row[0]) == -10000
    finally:
        cleanup_tenant(tenant)
