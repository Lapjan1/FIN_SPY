$ErrorActionPreference = 'Stop'
function Splice($file, $find, $replace) {
  $raw = [IO.File]::ReadAllText($file)
  $n = ([regex]::Matches($raw, [regex]::Escape($find))).Count
  if ($n -ne 1) { throw "$file : expected 1 match, found $n for: $($find.Substring(0, [Math]::Min(60, $find.Length)))" }
  [IO.File]::WriteAllText($file, $raw.Replace($find, $replace))
  Write-Output "OK $($file.Split('\')[-1]) :: $($find.Split("`r`n")[0].Trim().Substring(0, [Math]::Min(50, $find.Split("`r`n")[0].Trim().Length)))"
}
$NL = "`r`n"

# R1 auditor computation
Splice 'apps/api/reports.py' (
  @"
            # Convert amount_minor to Rands for auditor
            amount_rands = r.get('amount_minor',0)/100 if r.get('amount_minor') else 0
"@ -replace "`n", $NL
) (
  @"
            # Exponent-aware majors per row currency; amount_rands key kept
            # for importer compat, amount_display carries the symbol.
            ccy = r.get('currency', 'ZAR') or 'ZAR'
            amount_major = minor_to_major(r.get('amount_minor', 0) or 0, ccy)
"@ -replace "`n", $NL
)

# R2 auditor row values
Splice 'apps/api/reports.py' (
  @"
                "amount_rands": f"{amount_rands:.2f}",
                "currency": r.get('currency','ZAR'),
"@ -replace "`n", $NL
) (
  @"
                "amount_rands": f"{amount_major:.2f}",
                "currency": ccy,
"@ -replace "`n", $NL
)

# R3 auditor amount_display at row end
Splice 'apps/api/reports.py' (
  @"
                "doc_sha256": r.get('doc_sha256',''),
            })
"@ -replace "`n", $NL
) (
  @"
                "doc_sha256": r.get('doc_sha256',''),
                "amount_display": format_money(r.get('amount_minor', 0) or 0, ccy),
            })
"@ -replace "`n", $NL
)

# R4 cover signature
Splice 'apps/api/reports.py' (
  'def _wb_cover_summary(wb, bold, tenant_id, ts, from_date, to_date, data, money_fmt=None):'
) (
  'def _wb_cover_summary(wb, bold, tenant_id, ts, from_date, to_date, data, money_fmt=None, currency="ZAR"):'
)

# R5 cover money line + labels
Splice 'apps/api/reports.py' (
  @"
    ws.write(4, 0, "Money in rands (R, 2 decimals); formulas live - edit Journal, totals follow.")
"@ -replace "`n", $NL
) (
  @"
    sym = currency_symbol(currency)
    money_line = ("Money in rands (R, 2 decimals); formulas live - edit Journal, totals follow."
                  if currency == "ZAR" else
                  f"Money in {currency} ({sym}); formulas live - edit Journal, totals follow.")
    ws.write(4, 0, money_line)
"@ -replace "`n", $NL
)
Splice 'apps/api/reports.py' (
  '        ("Debits (R)", tot_d), ("Credits (R)", tot_c),'
) (
  '        (f"Debits ({sym})", tot_d), (f"Credits ({sym})", tot_c),'
)
Splice 'apps/api/reports.py' (
  '        if money_fmt is not None and k in ("Debits (R)", "Credits (R)"):'
) (
  '        if money_fmt is not None and k in (f"Debits ({sym})", f"Credits ({sym})"):'
)

# R6 workbook derive + pass
Splice 'apps/api/reports.py' (
  '    _wb_cover_summary(wb, bold, tenant_id, ts, from_date, to_date, data, money)'
) (
  @"
    ccys = {t.get("currency", "ZAR") or "ZAR" for t in data["txns"]}
    wb_ccy = ccys.pop() if len(ccys) == 1 else "ZAR"
    _wb_cover_summary(wb, bold, tenant_id, ts, from_date, to_date, data, money, wb_ccy)
"@ -replace "`n", $NL
)

# R7 dashboard select adds currency (main.py)
Splice 'apps/api/main.py' (
  '    q = "SELECT id, txn_date, description_raw, amount_minor, direction, account_number FROM transactions WHERE tenant_id=? AND status != ''rejected''"'
) (
  '    q = "SELECT id, txn_date, description_raw, amount_minor, currency, direction, account_number FROM transactions WHERE tenant_id=? AND status != ''rejected''"'
)

# R8 dashboard compute + return currency
Splice 'apps/api/main.py' (
  @"
    leak = kpis.get("subscription_creep_minor", 0) or 0
    return {
"@ -replace "`n", $NL
) (
  @"
    leak = kpis.get("subscription_creep_minor", 0) or 0
    ccys = {t.get("currency") or "ZAR" for t in txns}
    dash_ccy = ccys.pop() if len(ccys) == 1 else ("ZAR" if not ccys else "MULTI")
    return {
"@ -replace "`n", $NL
)
Splice 'apps/api/main.py' (
  @"
        "account_number": account_number,
        "active_template": active,
"@ -replace "`n", $NL
) (
  @"
        "account_number": account_number,
        "currency": dash_ccy,
        "active_template": active,
"@ -replace "`n", $NL
)
Write-Output 'ALL SPLICES DONE'
