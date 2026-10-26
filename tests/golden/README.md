# Golden Tests

Synthetic SA bank PDFs per `scripts/generate_sa_statements.py --banks FNB,STDB,ABSA --out data/samples/`

Each PDF has expected JSON: row accuracy >=99% digital, reconciliation pass 100% confirmed, 0 silent failures, every confirmed row has >=1 source_spans line_id+bbox.

Run: `uv run pytest tests/golden -v`

- `FNB_synthetic_*.csv` - FNB layout
- `STDB_synthetic_*.csv` - Standard Bank
- `ABSA_synthetic_*.csv` - Absa
- Adversarial: hidden text white/0pt, prompt injection strings in PDF, malformed, giant file, duplicate upload

Per homework Day3 Day8 acceptance targets: header fields >=99%, row amount/date exactness >=99% on synthetic set, 100% confirmed rows reconciled.
