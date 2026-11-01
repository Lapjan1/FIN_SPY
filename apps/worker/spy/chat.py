"""
Chat over DB: deterministic tools answer from tenant data, an LLM may only
rephrase provided facts - never invent numbers. Local-first: freellmapi then
ollama; with no model reachable the templated answer still goes out with
citations. No hosted calls, zero credit.
"""
from typing import List, Dict, Any
import json

from apps.worker.spy import detectors as det
from apps.worker.spy.kpi import compute_period_totals


def _rands(minor: int) -> str:
    return f"R{minor / 100:,.2f}"


def load_txns(tenant_id: str) -> List[Dict]:
    from apps.api.db import get_db
    db = get_db()
    cur = db.execute(
        "SELECT id, txn_date, description_raw, amount_minor, direction,"
        " document_id, fingerprint_sha256, status FROM transactions"
        " WHERE tenant_id=? AND status != 'rejected' ORDER BY txn_date DESC LIMIT 5000", (tenant_id,))
    return [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]


def load_flags(tenant_id: str, limit: int = 20) -> List[Dict]:
    from apps.api.db import get_db
    db = get_db()
    cur = db.execute(
        "SELECT id, test_id, severity, result_json, created_at FROM flags"
        " WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?", (tenant_id, limit))
    return [dict(r) if not isinstance(r, dict) else r for r in cur.fetchall()]


# --- tools: pure functions over tenant rows ---

def tool_totals(txns: List[Dict]) -> Dict[str, Any]:
    t = compute_period_totals(txns)
    return {"inflow_minor": t["inflow_minor"], "outflow_minor": t["outflow_minor"],
            "net_flow_minor": t["net_flow_minor"], "txn_count": t["txn_count"]}


def tool_top_vendors(txns: List[Dict], n: int = 5) -> List[Dict]:
    t = compute_period_totals(txns)
    ranked = sorted(t["vendor_counts"].items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"vendor": v, "amount_minor": a} for v, a in ranked]


def tool_search(txns: List[Dict], query: str, limit: int = 5) -> List[Dict]:
    q = (query or "").lower().strip()
    hits = [t for t in txns if q and q in (t.get("description_raw", "") or "").lower()]
    return [{"id": t["id"], "txn_date": t.get("txn_date"), "description": t.get("description_raw"),
             "amount_minor": t.get("amount_minor"), "direction": t.get("direction"),
             "document_id": t.get("document_id")} for t in hits[:limit]]


def tool_subscriptions(txns: List[Dict]) -> Dict[str, Any]:
    subs = det.detect_recurring(txns)
    return {"subscriptions": [
        {"merchant": s["merchant"], "monthly_cost_minor": s["monthly_cost_minor"],
         "occurrences": s["occurrences"], "tx_ids": s["tx_ids"]} for s in subs],
        "leak_per_month_minor": sum(s["monthly_cost_minor"] for s in subs)}


def tool_duplicates(txns: List[Dict]) -> List[Dict]:
    return det.detect_duplicate(txns)


def tool_fees(txns: List[Dict]) -> Dict[str, Any]:
    fees = det.detect_fee(txns)
    return {"fees": fees[:10], "count": len(fees),
            "total_minor": sum(f["amount_minor"] for f in fees)}


TOOLS = {
    "totals": ("Totals in/out/net for the tenant", tool_totals),
    "top_vendors": ("Top outflow vendors", tool_top_vendors),
    "search": ("Find transactions by description substring", tool_search),
    "subscriptions": ("Recurring subscriptions + leak per month", tool_subscriptions),
    "duplicates": ("Exact + 24h near duplicates", tool_duplicates),
    "fees": ("Bank/service fees (F-010)", tool_fees),
}


def openai_tool_schemas() -> List[Dict]:
    return [
        {"type": "function", "function": {"name": "totals", "description": TOOLS["totals"][0], "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "top_vendors", "description": TOOLS["top_vendors"][0], "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}}}},
        {"type": "function", "function": {"name": "search", "description": TOOLS["search"][0], "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "subscriptions", "description": TOOLS["subscriptions"][0], "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "duplicates", "description": TOOLS["duplicates"][0], "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {"name": "fees", "description": TOOLS["fees"][0], "parameters": {"type": "object", "properties": {}}}},
    ]


def run_tool(name: str, txns: List[Dict], args: Dict[str, Any]) -> Any:
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    fn = TOOLS[name][1]
    if name == "search":
        return fn(txns, str(args.get("query", "")))
    if name == "top_vendors":
        try:
            n = max(1, min(int(args.get("n", 5)), 20))
        except (TypeError, ValueError):
            n = 5
        return fn(txns, n)
    return fn(txns)


# --- intent router: deterministic facts + templated answer ---

def _cite_txns(rows: List[Dict]) -> List[Dict]:
    cites = []
    for t in rows[:5]:
        tid = t.get("id") or t.get("tx_id")
        if tid:
            cites.append({"txn_id": tid, "document_id": t.get("document_id")})
    return cites


def _intent_subscriptions(txns: List[Dict]) -> Dict[str, Any]:
    out = tool_subscriptions(txns)
    cites = [{"txn_id": tid} for s in out["subscriptions"] for tid in s["tx_ids"][:2]]
    if not out["subscriptions"]:
        text = "No recurring subscriptions found (needs 3+ monthly charges within 5% amount)."
    else:
        lines = [f"- {s['merchant']}: {_rands(s['monthly_cost_minor'])}/mo x{s['occurrences']}" for s in out["subscriptions"]]
        text = f"Subscriptions leaking {_rands(out['leak_per_month_minor'])}/mo:\n" + "\n".join(lines)
    return {"answer": text, "tool_calls": [{"tool": "subscriptions", "result": out}], "citations": cites}


def _intent_duplicates(txns: List[Dict]) -> Dict[str, Any]:
    out = tool_duplicates(txns)
    text = "No duplicates found." if not out else (
        f"{len(out)} possible duplicates:\n" + "\n".join(
            f"- {d.get('code')}: {d.get('tx_id')} dup of {d.get('dup_of')}" for d in out[:8]))
    return {"answer": text, "tool_calls": [{"tool": "duplicates", "result": out}],
            "citations": _cite_txns(out)}


def _intent_fees(txns: List[Dict]) -> Dict[str, Any]:
    out = tool_fees(txns)
    text = "No bank fees found." if out["count"] == 0 else (
        f"{out['count']} fees totalling {_rands(out['total_minor'])} (F-010).")
    return {"answer": text, "tool_calls": [{"tool": "fees", "result": out}],
            "citations": _cite_txns(out["fees"])}


def _intent_top_vendors(txns: List[Dict]) -> Dict[str, Any]:
    out = tool_top_vendors(txns)
    text = "No outflows yet." if not out else (
        "Top vendors by outflow:\n" + "\n".join(
            f"- {v['vendor']}: {_rands(v['amount_minor'])}" for v in out))
    return {"answer": text, "tool_calls": [{"tool": "top_vendors", "result": out}], "citations": []}


def _intent_flags(flags: List[Dict]) -> Dict[str, Any]:
    if not flags:
        return {"answer": "No spy flags stored - run the spy first (POST /v1/spy/run).",
                "tool_calls": [], "citations": []}
    lines = [f"- {f.get('test_id')} [{f.get('severity')}]: {(f.get('result_json') or '')[:100]}" for f in flags[:8]]
    return {"answer": f"{len(flags)} flags:\n" + "\n".join(lines),
            "tool_calls": [], "citations": []}


def _intent_spend(question: str, txns: List[Dict]) -> Dict[str, Any] | None:
    # "spend on X" / "spent at X": merchant search from trailing words
    query = question.replace("spend", "").replace("spent", "").replace("on", "").replace("at", "").strip()
    if not query:
        return None
    out = tool_search(txns, query)
    total = sum(t["amount_minor"] for t in out if t.get("direction") == "debit")
    text = f"No spend found for '{query}'." if not out else (
        f"Spent {_rands(total)} across {len(out)} matching transactions for '{query}'.")
    return {"answer": text, "tool_calls": [{"tool": "search", "result": out}],
            "citations": _cite_txns(out)}


def _intent_totals(txns: List[Dict]) -> Dict[str, Any]:
    out = tool_totals(txns)
    text = (f"Totals over {out['txn_count']} transactions: in {_rands(out['inflow_minor'])}, "
            f"out {_rands(out['outflow_minor'])}, net {_rands(out['net_flow_minor'])}. "
            f"Ask about top vendors, subscriptions, duplicates, fees, flags, or spend on X.")
    return {"answer": text, "tool_calls": [{"tool": "totals", "result": out}], "citations": []}


def answer_intent(question: str, txns: List[Dict], flags: List[Dict]) -> Dict[str, Any]:
    q = (question or "").lower()
    if any(w in q for w in ("subscri", "recurring", "leak")):
        return _intent_subscriptions(txns)
    if "duplic" in q:
        return _intent_duplicates(txns)
    if any(w in q for w in ("fee", "charge", "commission")):
        return _intent_fees(txns)
    if any(w in q for w in ("top", "vendor", "merchant", "biggest", "largest")):
        return _intent_top_vendors(txns)
    if "flag" in q:
        return _intent_flags(flags)
    if any(w in q for w in ("spend", "spent")) and len(q.split()) <= 6:
        found = _intent_spend(q, txns)
        if found:
            return found
    return _intent_totals(txns)


def _is_mock(result) -> bool:
    usage = getattr(result, "usage", None) or {}
    if isinstance(usage, dict) and usage.get("error"):
        return True
    return (getattr(result, "content", "") or "").startswith("Mock completion")


def _reachable(base_url: str, timeout_s: float = 1.0) -> bool:
    """Fast TCP pre-check so a dead local model fails in ~1s, not after
    SDK retries. Never blocks the deterministic answer path."""
    import socket
    from urllib.parse import urlparse
    try:
        parts = urlparse(base_url)
        host, port = parts.hostname or "127.0.0.1", parts.port or 80
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _live_model_answer(question: str, facts: Dict[str, Any], tenant_id: str = "default"):
    """Ask a local model to rephrase deterministic facts. Returns None when
    no model is reachable (mock responses never surface as answers)."""
    from apps.worker.llm.client import MetaClient, resolve_model
    prompt = ("Answer the user question using ONLY these tool facts. "
              "Never invent numbers; keep citations.\n"
              f"Question: {question}\nFacts: {json.dumps(facts)[:4000]}")
    _rp, _rm = resolve_model("chat")
    _chain = [(_rp, _rm)]
    if (_rp, _rm) != ("ollama", "llama3.2:latest"):
        _chain.append(("ollama", "llama3.2:latest"))  # privacy fallback
    for provider, model in _chain:

        try:
            client = MetaClient(provider=provider, model_id=model)
            if not _reachable(client.base_url):
                continue
            res = client.complete(
                [{"role": "system", "content": "Forensic bookkeeping assistant. Answer only from supplied facts."},
                 {"role": "user", "content": prompt}], effort="low", tenant_id=tenant_id)
            if _is_mock(res):
                continue
            if res.tool_calls:
                return {"content": None, "tool_calls": res.tool_calls,
                        "model_id": res.model_id}
            if (res.content or "").strip():
                return {"content": res.content.strip(), "tool_calls": [],
                        "model_id": res.model_id}
        except Exception:
            continue
    return None


def chat_answer(tenant_id: str, question: str) -> Dict[str, Any]:
    txns = load_txns(tenant_id)
    flags = load_flags(tenant_id)
    if not txns:
        return {"answer": "No transactions yet - upload a statement first.",
                "tool_calls": [], "citations": [], "model": "none"}
    facts = answer_intent(question, txns, flags)
    facts_payload = {c["tool"]: c["result"] for c in facts["tool_calls"]}
    if not facts_payload:
        facts_payload = {"flags": [f.get("test_id") for f in flags[:8]]}
    live = _live_model_answer(question, facts_payload, tenant_id)
    if live is None:
        return {**facts, "model": "deterministic (no local model reachable)"}
    if live["content"]:
        return {"answer": live["content"], "tool_calls": facts["tool_calls"],
                "citations": facts["citations"], "model": live["model_id"]}
    # Model requested tools: execute up to 4, then rephrase from results
    executed = []
    for tc in (live["tool_calls"] or [])[:4]:
        try:
            args = json.loads(tc.get("arguments", "{}") or "{}")
        except Exception:
            args = {}
        executed.append({"tool": tc.get("name"),
                         "result": run_tool(tc.get("name", ""), txns, args)})
    if not executed:
        return {**facts, "model": live["model_id"]}
    second = _live_model_answer(
        question, {e["tool"]: e["result"] for e in executed}, tenant_id)
    if second and second["content"]:
        return {"answer": second["content"], "tool_calls": executed,
                "citations": facts["citations"], "model": live["model_id"]}
    return {**facts, "model": live["model_id"]}
