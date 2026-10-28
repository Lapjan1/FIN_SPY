"""
Day5 spy + KPI + debt: detectors real (no [] stubs), Decimal amortization,
leak score wired to KPIs, endpoints live.
Per docs/TIMELINE.md Day5: subscriptions duplicates F-010 fee Benford F-020
leak R/mo, KPIs, snowball vs avalanche, R45k/R20k/R10k fixture ordering.
"""
import uuid
from decimal import Decimal

from apps.api.db import init_db, get_db, cleanup_tenant
from apps.worker.spy import detectors as det
from apps.worker.spy.debt import Debt, plan_debts, what_if_extra
from apps.worker.spy.kpi import compute_kpis


def _tx(desc, amount_minor, date, direction="debit", fp=None, i=0):
    return {"id": f"tx-{i}-{uuid.uuid4().hex[:6]}", "txn_date": date,
            "description_raw": desc, "amount_minor": amount_minor,
            "direction": direction,
            "fingerprint_sha256": fp or f"fp-{uuid.uuid4().hex[:8]}"}


def _debts_45_20_10():
    # R45k@21%, R20k@18%, R10k@9%: snowball != avalanche order
    return [Debt("Bank45", 4500000, Decimal("21"), 120000),
            Debt("Store20", 2000000, Decimal("18"), 80000),
            Debt("Card10", 1000000, Decimal("9"), 50000)]


# --- detectors ---

def test_recurring_detects_monthly_subscription():
    txns = [_tx("NETFLIX.COM", 19999, "2026-01-05", i=1),
            _tx("NETFLIX.COM", 19999, "2026-02-04", i=2),
            _tx("NETFLIX.COM", 19999, "2026-03-06", i=3)]
    subs = det.detect_recurring(txns)
    assert len(subs) == 1
    assert subs[0]["code"] == "SUB"
    assert subs[0]["occurrences"] == 3
    assert subs[0]["monthly_cost_minor"] == 19999
    assert subs[0]["cadence_days"] == 30


def test_recurring_amount_tolerance_and_minimum():
    tol = [_tx("SPOTIFY", 19999, "2026-01-05", i=1),
           _tx("Spotify", 20500, "2026-02-04", i=2),
           _tx("SPOTIFY", 19400, "2026-03-06", i=3)]
    assert len(det.detect_recurring(tol)) == 1  # within +/-5%
    two = tol[:2]
    assert det.detect_recurring(two) == []  # <3 occurrences
    inflow = [_tx("SALARY", 500000, "2026-01-05", direction="credit", i=i)
              for i in range(1, 4)]
    assert det.detect_recurring(inflow) == []  # outflows only


def test_duplicate_exact_and_near():
    txns = [_tx("WOOLWORTHS", 50000, "2026-01-05", fp="same-fp", i=1),
            _tx("WOOLWORTHS", 50000, "2026-01-05", fp="same-fp", i=2),
            _tx("ENGEN", 80000, "2026-02-01", fp="fp-a", i=3),
            _tx("ENGEN", 80000, "2026-02-02", fp="fp-b", i=4)]
    dups = det.detect_duplicate(txns)
    codes = [d["code"] for d in dups]
    assert "DUP" in codes
    assert "NDUP" in codes
    assert det.detect_duplicate(txns[:1]) == []


def test_fee_f010():
    txns = [_tx("Monthly account fee", 9900, "2026-01-05", i=1),
            _tx("WOOLWORTHS", 50000, "2026-01-06", i=2)]
    fees = det.detect_fee(txns)
    assert len(fees) == 1
    assert fees[0]["code"] == "F-010"
    assert fees[0]["amount_minor"] == 9900


def test_anomaly_iqr_flags_outlier():
    txns = [_tx("WOOLWORTHS", 50000, f"2026-01-{5 + i:02d}", i=i) for i in range(1, 7)]
    txns.append(_tx("WOOLWORTHS", 900000, "2026-02-01", i=7))
    flags = det.detect_anomaly_iqr(txns)
    assert len(flags) == 1
    assert flags[0]["code"] == "F-030"
    assert flags[0]["amount_minor"] == 900000
    assert flags[0]["tx_id"] == txns[-1]["id"]
    assert det.detect_anomaly_iqr(txns[:4]) == []  # <5 needs no stats


def test_benford_flags_gamed_books():
    gamed = [_tx(f"VENDOR {i}", 90000 + i * 100, "2026-01-05", i=i) for i in range(25)]
    flags = det.detect_benford(gamed)
    assert len(flags) == 1
    assert flags[0]["code"] == "BEN"
    assert flags[0]["digit_one_share"] == 0
    assert det.detect_benford(gamed[:5]) == []  # n<20 no verdict


def test_leak_score_and_kpi_wiring():
    txns = [_tx("NETFLIX.COM", 19999, "2026-01-05", i=1),
            _tx("NETFLIX.COM", 19999, "2026-02-04", i=2),
            _tx("NETFLIX.COM", 19999, "2026-03-06", i=3),
            _tx("SALARY", 500000, "2026-03-01", direction="credit", i=4)]
    assert det.leak_score_per_month(txns) == 19999
    kpis = compute_kpis(txns)
    assert kpis["subscription_creep_minor"] == 19999


# --- debt ---

def test_debt_fixture_ordering_45_20_10():
    debts = _debts_45_20_10()
    snow = plan_debts(debts, 0, "snowball")
    aval = plan_debts(debts, 0, "avalanche")
    assert snow["order"] == ["Card10", "Store20", "Bank45"]
    assert aval["order"] == ["Bank45", "Store20", "Card10"]
    assert snow["months"] > 0 and aval["months"] > 0
    assert aval["total_interest_minor"] <= snow["total_interest_minor"]
    assert aval["interest_saved_minor"] >= 0
    assert snow["interest_saved_minor"] <= 0


def test_debt_what_if_and_edges():
    debts = _debts_45_20_10()
    w = what_if_extra(debts, 100000, "snowball")
    assert w["boosted_months"] < w["base_months"]
    assert w["interest_saved_minor"] > 0
    assert plan_debts([], 0)["months"] == 0
    stuck = plan_debts([Debt("X", 100000, Decimal("24"), 0)], 0)
    assert stuck["warnings"], "zero payments must warn, not loop"


# --- endpoints ---

def _authed(prefix="spy5"):
    from fastapi.testclient import TestClient
    from apps.api.main import app
    client = TestClient(app)
    init_db()
    tenant = f"{prefix}-{uuid.uuid4().hex[:6]}"
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    client.post("/v1/auth/register",
                json={"email": email, "password": "pass1234",
                      "name": "T", "tenant_id": tenant})
    r = client.post("/v1/auth/login", json={"email": email, "password": "pass1234"})
    return client, tenant, {"X-User-Id": str(r.json()["id"])}


def test_debt_plan_endpoint_real_maths():
    client, tenant, h = _authed()
    try:
        body = {"method": "avalanche", "extra_cash_per_month_minor": 50000,
                "debts": [{"creditor": "Bank45", "balance_minor": 4500000,
                           "apr_pct": "21", "min_payment_minor": 120000},
                          {"creditor": "Card10", "balance_minor": 1000000,
                           "apr_pct": "9", "min_payment_minor": 50000}]}
        r = client.post("/v1/debt/plan", json=body, headers=h)
        assert r.status_code == 200
        out = r.json()
        assert out["order"] == ["Bank45", "Card10"]
        assert out["months"] > 0
        assert out["total_interest_minor"] > 0
        assert "what_if" in out
        bad = client.post("/v1/debt/plan",
                          json={"method": "snowball",
                                "extra_cash_per_month_minor": -1,
                                "debts": body["debts"]}, headers=h)
        assert bad.status_code == 422
    finally:
        cleanup_tenant(tenant)


def test_spy_run_persists_flags_idempotent():
    client, tenant, h = _authed()
    try:
        db = get_db()
        rows = [("NETFLIX.COM", 19999, "2026-01-05"),
                ("NETFLIX.COM", 19999, "2026-02-04"),
                ("NETFLIX.COM", 19999, "2026-03-06"),
                ("Monthly account fee", 9900, "2026-03-01")]
        for i, (desc, amt, date) in enumerate(rows):
            db.execute(
                "INSERT INTO transactions (id, tenant_id, txn_date, description_raw,"
                " amount_minor, direction, fingerprint_sha256, status)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (f"spy5-{i}-{uuid.uuid4().hex[:6]}", tenant, date, desc, amt,
                 "debit", f"sp5-{uuid.uuid4().hex[:8]}", "confirmed"))
        db.commit()
        r = client.post("/v1/spy/run", headers=h)
        assert r.status_code == 200
        out = r.json()
        assert out["txn_count"] == 4
        assert out["by_code"].get("SUB") == 1
        assert out["by_code"].get("F-010") == 1
        assert out["by_code"].get("F-020") == 1
        assert out["leak_per_month_minor"] == 19999
        r2 = client.get("/v1/flags", headers=h)
        assert r2.status_code == 200
        n1 = len(r2.json())
        assert n1 >= 3
        # Re-run overwrites, never duplicates
        client.post("/v1/spy/run", headers=h)
        assert len(client.get("/v1/flags", headers=h).json()) == n1
    finally:
        cleanup_tenant(tenant)
