"""
Generate synthetic SA bank statements PDFs + CSVs for golden tests per homework Day0.
Never real customer data. Handles SA formats: R prefix, space thousands, comma decimals, (450), Cr/Dr, multiple banks.
Usage: python scripts/generate_sa_statements.py --banks FNB,STDB,ABSA --out data/samples/
"""
import argparse
import csv
import random
from pathlib import Path
from datetime import date, timedelta

BANKS = ["FNB","STDB","ABSA","Nedbank","Capitec"]

def gen_transactions(n=50):
    base = date.today() - timedelta(days=90)
    merchants = ["WOOLWORTHS","CHECKERS","SPAR","SHELL FUEL","VODACOM","NETFLIX","UBER","MUNICIPALITY","SARS","PAYSTACK FEE","BANK CHARGE","RENT","SALARY","INTEREST"]
    rows = []
    bal = 12340.55
    for i in range(n):
        d = base + timedelta(days=i*2)
        desc = random.choice(merchants)
        amt = round(random.uniform(-1500, -10) if random.random()>0.3 else random.uniform(500, 5000), 2)
        if "SALARY" in desc:
            amt = abs(amt)*5
        bal += amt
        # SA format variations
        raw_amt = f"R {abs(amt):,.2f}".replace(","," ").replace(".",",") if random.random()>0.5 else f"{amt:.2f}"
        if amt<0 and random.random()>0.7:
            raw_amt = f"({raw_amt})"
        rows.append({"date": d.isoformat(),"desc": desc,"amount": raw_amt,"amount_minor": int(amt*100),"balance": round(bal,2),"line_id": f"L{i+1:03d}"})
    # Inject duplicates per spy test
    if rows:
        dup = rows[5].copy()
        dup["date"] = (date.fromisoformat(rows[5]["date"]) + timedelta(days=1)).isoformat()
        rows.append(dup)
    return rows, 12340.55, bal

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banks", default="FNB,STDB,ABSA")
    ap.add_argument("--out", default="data/samples/")
    ap.add_argument("--count", type=int, default=5)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    banks = args.banks.split(",")
    for bank in banks:
        for j in range(args.count):
            rows, opening, closing = gen_transactions(60)
            # CSV
            csv_path = out / f"{bank}_synthetic_{j+1}.csv"
            with csv_path.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=["date","desc","amount","amount_minor","balance","line_id"])
                w.writeheader()
                for r in rows:
                    w.writerow(r)
            # Minimal PDF placeholder - real PDF generation would need ReportLab
            pdf_placeholder = out / f"{bank}_synthetic_{j+1}.txt"
            pdf_placeholder.write_text(f"Bank: {bank} Opening: {opening} Closing: {closing}\n" + "\n".join([f"{r['line_id']} | {r['date']} | {r['desc']} | {r['amount']} | {r['balance']}" for r in rows]))
            print(f"Generated {csv_path} and {pdf_placeholder} opening {opening} closing {closing}")
    print("Synthetic generation done. For hackathon demo, use CSVs as fallback, build PDF via ReportLab later.")

if __name__ == "__main__":
    main()
