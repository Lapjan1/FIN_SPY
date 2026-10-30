"""CSV sniff tolerates ragged preamble/trailer lines: titled bank CSVs
must parse as CSV (vault-realistic .pdf suffix), not fall to splitlines
where raw commas fuse amounts and extraction finds nothing."""

from apps.worker.parsers.extractor import extract_document, _looks_csv

TITLED = (
    "FNB Statement Account Number 62123456789\n"
    "Opening Balance: R12 340.55\n"
    "Date,Description,Amount,Balance\n"
    "25 Oct 2026,WOOLWORTHS,-450.00,11550.00\n"
    "26 Oct 2026,RENT,-5000.00,6550.00\n"
    "27 Oct 2026,SALARY,20000.00,26550.00\n"
    "28 Oct 2026,SPAR,-300.00,26250.00\n"
    "29 Oct 2026,UBER,-150.00,26100.00\n"
    "30 Oct 2026,NETFLIX,-200.00,25900.00\n"
    "Closing Balance: R12 310.55\n"
)

UNIFORM = (
    "Date,Description,Amount,Balance\n"
    "25 Oct 2026,WOOLWORTHS,-450.00,11550.00\n"
    "26 Oct 2026,RENT,-5000.00,6550.00\n"
    "27 Oct 2026,SALARY,20000.00,26550.00\n"
    "28 Oct 2026,SPAR,-300.00,26250.00\n"
    "29 Oct 2026,UBER,-150.00,26100.00\n"
    "30 Oct 2026,NETFLIX,-200.00,25900.00\n"
)

PROSE = (
    "Dear sir, please find the attached note about cats, dogs, birds\n"
    "and other animals we discussed on Tuesday at length indeed\n"
    "yours faithfully, someone with no tables at all here\n"
)


def test_sniff_accepts_titled_csv():
    assert _looks_csv(TITLED) is True


def test_sniff_still_accepts_uniform_csv():
    assert _looks_csv(UNIFORM) is True


def test_sniff_still_rejects_prose():
    assert _looks_csv(PROSE) is False


def test_titled_csv_extracts_rows(tmp_path):
    # Vault-realistic: CSV bytes under a .pdf-suffixed key.
    p = tmp_path / "abc123.pdf"
    p.write_text(TITLED, encoding="utf-8")
    result = extract_document(p, bank_hint="FNB", tenant_id="sniff")
    assert len(result.rows) >= 4, (
        f"expected chained rows, got {len(result.rows)}: "
        f"{result.warnings[:2]}")
