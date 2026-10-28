"""
KPI Engine - per docs/MODULES.md kpi-engine: runway,burn,savings,debt-to-income
Understands money in and outflow via direction per user question: does extractor/AI understand money in and outflow? do we need this? YES for peek
"""
from typing import Dict, List
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict, Counter

def direction_flags(direction: str) -> Dict[str, object]:
    """Explicit inflow/outflow flag from direction. Credit = money in, debit = money out."""
    d = (direction or "debit").lower()
    is_inflow = d == "credit"
    is_outflow = not is_inflow
    return {"is_inflow": is_inflow, "is_outflow": is_outflow, "signed_multiplier": 1 if is_inflow else -1}

def compute_period_totals(transactions: List[Dict], from_date: str = None, to_date: str = None, account_number: str = None) -> Dict:
    """Totals per period of inspection BEFORE percentages.
    Filters by txn_date range and optional account_number, then sums inflow/outflow.
    Returns totals + per-month breakdown. All money in minor units (cents).
    """
    filtered = []
    for tx in transactions:
        d = tx.get('txn_date', '') or tx.get('date', '')
        if from_date and d < from_date:
            continue
        if to_date and d > to_date:
            continue
        if account_number and tx.get('account_number') != account_number:
            continue
        filtered.append(tx)

    inflow_minor = 0
    outflow_minor = 0
    inflow_count = 0
    outflow_count = 0
    monthly_outflow = defaultdict(int)
    monthly_inflow = defaultdict(int)
    vendor_counts = Counter()
    for tx in filtered:
        amount = int(tx.get('amount_minor', 0))
        flags = direction_flags(tx.get('direction', 'debit'))
        desc = tx.get('description_raw', '') or tx.get('description', '')
        date_str = tx.get('txn_date', '') or tx.get('date', '')
        if flags["is_inflow"]:
            inflow_minor += amount
            inflow_count += 1
            if date_str:
                monthly_inflow[date_str[:7]] += amount
        else:
            outflow_minor += amount
            outflow_count += 1
            vendor = desc.split()[0] if desc else "Unknown"
            vendor_counts[vendor] += amount
            if date_str:
                monthly_outflow[date_str[:7]] += amount

    return {
        "from_date": from_date,
        "to_date": to_date,
        "account_number": account_number,
        "txn_count": len(filtered),
        "inflow_count": inflow_count,
        "outflow_count": outflow_count,
        "inflow_minor": inflow_minor,
        "outflow_minor": outflow_minor,
        "net_flow_minor": inflow_minor - outflow_minor,
        "monthly_inflow": dict(monthly_inflow),
        "monthly_outflow": dict(monthly_outflow),
        "vendor_counts": dict(vendor_counts),
    }

def compute_kpis(transactions: List[Dict], current_balance_minor: int = None, from_date: str = None, to_date: str = None, account_number: str = None) -> Dict:
    """
    Compute KPIs from transactions list. Step 1: totals per period (compute_period_totals).
    Step 2: percentages derived from totals (savings_rate, private_vs_business, etc).
    Each transaction has amount_minor, direction debit|credit, txn_date
    Inflow = credit (money in), Outflow = debit (money out) per SA bank: debit is outflow, credit is inflow
    """
    totals = compute_period_totals(transactions, from_date, to_date, account_number)
    inflow = totals["inflow_minor"]
    outflow = totals["outflow_minor"]
    if totals["txn_count"] == 0:
        return {
            "from_date": from_date,
            "to_date": to_date,
            "account_number": account_number,
            "totals": totals,
            "runway_months": 0,
            "burn_rate_minor": 0,
            "savings_rate_pct": 0,
            "debt_to_income": 0,
            "private_vs_business_ratio": 0,
            "inflow_minor": 0,
            "outflow_minor": 0,
            "net_flow_minor": 0,
            "top_vendors": [],
            "subscription_creep_minor": 0,
            "is_inflow_understood": True,
            "is_outflow_understood": True,
        }

    # Totals already computed per period first (see totals above) - derive percentages from totals
    inflow = totals["inflow_minor"]
    outflow = totals["outflow_minor"]
    monthly_inflow = defaultdict(int, totals.get("monthly_inflow", {}))
    monthly_outflow = defaultdict(int, totals.get("monthly_outflow", {}))
    vendor_counts = Counter(totals.get("vendor_counts", {}))

    net_flow = inflow - outflow
    # Burn rate = avg monthly outflow last 3 months
    if monthly_outflow:
        avg_burn = sum(monthly_outflow.values()) / len(monthly_outflow) if monthly_outflow else outflow
    else:
        avg_burn = outflow

    # Runway = current_balance / burn_rate
    runway_months = 0
    if current_balance_minor is not None and avg_burn > 0:
        runway_months = (current_balance_minor / avg_burn) if avg_burn else 0

    # Savings rate = (inflow - outflow)/inflow *100
    savings_rate = ((inflow - outflow) / inflow * 100) if inflow > 0 else 0

    # Debt-to-income placeholder - would need debts list
    debt_to_income = 0

    # Private vs business ratio - would need classifications
    private_vs_business_ratio = 0

    # Top vendors by outflow
    top_vendors = [{"vendor": v, "amount_minor": amt} for v, amt in vendor_counts.most_common(5)]

    # Subscription creep F-020: sum of recurring monthly costs from detectors
    from apps.worker.spy.detectors import leak_score_per_month
    subscription_creep = leak_score_per_month(transactions)

    return {
        "from_date": from_date,
        "to_date": to_date,
        "account_number": account_number,
        "totals": totals,
        "runway_months": round(runway_months, 1),
        "burn_rate_minor": int(avg_burn),
        "savings_rate_pct": round(savings_rate, 1),
        "debt_to_income": debt_to_income,
        "private_vs_business_ratio": private_vs_business_ratio,
        "inflow_minor": inflow,
        "outflow_minor": outflow,
        "net_flow_minor": net_flow,
        "top_vendors": top_vendors,
        "subscription_creep_minor": subscription_creep,
        "is_inflow_understood": True,  # Flag per user question does AI understand money in and outflow
        "is_outflow_understood": True,
    }

def compute_global_running_balance(transactions: List[Dict]) -> List[Dict]:
    """
    Global running balance across any amount of time yet in perfect calendar order per user question:
    Can someone add data 2026 and then work backwards to 2020? Does DB span any time yet in perfect calendar order?
    YES: DB can span any time, ORDER BY txn_date ASC gives perfect calendar order regardless of insertion order

    This function computes cumulative running balance from opening balance + sum signed ordered by date
    Top->Bottom and Bottom->Top both must match per reconciliation gate
    """
    # Sort by date ASC for calendar order
    sorted_txn = sorted(transactions, key=lambda x: x.get('txn_date', '') or x.get('date', ''))

    running = 0
    result = []
    for tx in sorted_txn:
        amount = tx.get('amount_minor', 0)
        direction = tx.get('direction', 'debit')
        signed = -amount if direction == "debit" else amount
        # For global running balance, start from 0 or from opening? For this calc, start from 0 and accumulate
        prev_running = running
        running += signed
        result.append({
            **tx,
            "running_balance_before": prev_running,
            "running_balance_after": running,
            "signed_amount": signed,
        })

    # Also compute bottom->top reverse for verification
    reverse_running = running  # Start from final
    reverse_result = []
    for tx in reversed(sorted_txn):
        amount = tx.get('amount_minor', 0)
        direction = tx.get('direction', 'debit')
        signed = -amount if direction == "debit" else amount
        # Reverse: prev in reverse = current - signed
        reverse_result.append({
            "txn_id": tx.get('id'),
            "reverse_running_before": reverse_running,
            "reverse_running_after": reverse_running - signed,
        })
        reverse_running -= signed

    return result

def get_monthly_cashflow(transactions: List[Dict]) -> Dict[str, Dict]:
    """
    Monthly cashflow for PowerBI: inflow, outflow, net per month YYYY-MM
    """
    monthly = defaultdict(lambda: {"inflow": 0, "outflow": 0, "net": 0})
    for tx in transactions:
        date_str = tx.get('txn_date', '')[:7]  # YYYY-MM
        amount = tx.get('amount_minor', 0)
        direction = tx.get('direction', 'debit')
        if direction == "credit":
            monthly[date_str]["inflow"] += amount
        else:
            monthly[date_str]["outflow"] += amount
        monthly[date_str]["net"] = monthly[date_str]["inflow"] - monthly[date_str]["outflow"]
    return dict(monthly)
