# FIX: Text-Reader for CSV/TXT/OFX Uploads — Task Document

## Goal
Intake accepts `.csv/.ofx` but the worker was PDF-only: CSV bytes hit
PyMuPDF/pdfplumber and died with `RuntimeError(Both ... failed)` —
0 rows, doc `exception`. Found by the live GUI audit (37/40).

## Red
New `tests/test_text_upload.py`: `extract_text_lines` missing
(collection error), then generic chaining 0 candidates on raw CSV lines.

## Implement (`apps/worker/parsers/extractor.py`)
- `extract_text_lines()`: same pages shape as the PDF reader (one page,
  Lxxx ids, text_hash, placeholder bbox) so bank/generic/LLM stages run
  unchanged. UTF-8-SIG decode, blank lines skipped.
- CSV cells parsed with `csv` + space-joined: raw commas fuse adjacent
  amounts into one SA token (`298.94,9701.06` unparseable); spaces keep
  them apart. ISO leading signs (`-298.94`) stripped — direction comes
  from balance chaining, and strays would pollute descriptions.
- `extract_document` dispatches on content sniff (`%PDF` magic), never
  the suffix: vault keys always end `.pdf` even for CSV bytes.
  `_looks_csv()` (2+ lines, shared 3+ cell count) picks the CSV path so
  TXT amounts like `R 1 356,88` are never shredded. Non-decodable
  binaries fail with a clear image-needs-OCR message instead of burning
  LLM money on garbage.

## Green
- `tests/test_text_upload.py`: 4 passed (shape, generic chains 4 rows
  with correct debit/credit, dispatch incl. vault-`.pdf` name).
- Full suite: 259 passed at commit `4d8e72c`.
- Live: synthetic FNB CSV → 48 proposed rows in seconds (audit 44/44).
