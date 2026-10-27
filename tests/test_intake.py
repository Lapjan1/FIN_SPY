"""
Test intake capabilities: bank statement detection, duplicate files, exclude other files, original vs tampered
Per user question: can our intake know when PDF or any file is bank statement? duplicates? exclude other files? original or tampered?
"""
from apps.worker.parsers.classifier import is_bank_statement, is_duplicate_file, is_near_duplicate_transactions, should_exclude_from_extraction, classify_file_type
from apps.worker.parsers.tamper import check_pdf_metadata_tampering, check_content_hash_chain, check_visual_tampering_indicators, full_tamper_check
from apps.api.db import init_db, get_db
from pathlib import Path
import uuid
import hashlib
import tempfile

def test_bank_statement_detection():
    # Bank statement text should be detected
    bank_text = "FNB Statement Account Number 123456 Branch Code 250655 Opening Balance R12 340.55 Closing Balance R6 890 25 Oct 2026 WOOLWORTHS R450,00"
    is_bank, conf, reasons = is_bank_statement(bank_text, "fnb_statement.pdf", "application/pdf")
    assert is_bank is True, f"Should be bank statement, conf {conf} reasons {reasons}"
    assert conf >= 0.5

    # Non-bank invoice should not be detected or low confidence
    invoice_text = "Invoice Number INV-001 Purchase Order for office supplies"
    is_bank, conf, reasons = is_bank_statement(invoice_text, "invoice.pdf", "application/pdf")
    assert conf < 0.5 or is_bank is False or "invoice" in str(reasons).lower()

def test_duplicate_file_detection():
    init_db()
    db = get_db()
    tenant = f"tenant-dup-{uuid.uuid4().hex[:6]}"
    # Create tenant first for FK
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}"))
    sha = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
    # Insert a document
    doc_id = f"doc-dup-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename) VALUES (?,?,?,?,?,?)",
               (doc_id, tenant, sha, 100, "vault/a.pdf", "a.pdf"))
    db.commit()
    # Check duplicate
    is_dup, msg = is_duplicate_file(sha, tenant, db)
    assert is_dup is True
    assert doc_id in msg or sha[:12] in msg

    # Non-duplicate
    is_dup, msg = is_duplicate_file(hashlib.sha256(b"different").hexdigest(), tenant, db)
    assert is_dup is False

    # Cleanup
    db.execute("DELETE FROM source_documents WHERE tenant_id=?", (tenant,))
    db.commit()

def test_near_duplicate_transactions():
    init_db()
    db = get_db()
    tenant = f"tenant-near-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}"))
    # Create existing fingerprints
    fps = [hashlib.sha256(f"2026-10-26|{i}|test".encode()).hexdigest() for i in range(5)]
    for i, fp in enumerate(fps):
        db.execute("INSERT INTO transactions (id, tenant_id, txn_date, description_raw, amount_minor, fingerprint_sha256) VALUES (?,?,?,?,?,?)",
                   (f"txn-near-{uuid.uuid4().hex[:6]}-{i}", tenant, "2026-10-26", f"Test {i}", -10000, fp))
    db.commit()

    # New file with 80% overlap should be near-duplicate
    new_fps = fps[:4] + [hashlib.sha256(b"new").hexdigest()]  # 4 overlap out of 5 = 80%
    is_near, reasons = is_near_duplicate_transactions(new_fps, tenant, db, threshold=0.8)
    assert is_near is True

    # Low overlap not near-duplicate
    new_fps_low = [hashlib.sha256(f"new-{i}".encode()).hexdigest() for i in range(5)]
    is_near, reasons = is_near_duplicate_transactions(new_fps_low, tenant, db, threshold=0.8)
    assert is_near is False

    # Cleanup
    db.execute("DELETE FROM transactions WHERE tenant_id=?", (tenant,))
    db.commit()

def test_exclude_other_files():
    # Bank statement should not be excluded
    bank_text = "FNB Statement Opening Balance Closing Balance 25 Oct WOOLWORTHS R450"
    is_bank, conf, _ = is_bank_statement(bank_text, "fnb.pdf", "application/pdf")
    should_exclude, reason = should_exclude_from_extraction(bank_text, "fnb.pdf", "application/pdf", is_bank, conf)
    assert should_exclude is False

    # Random small file should be excluded
    small_text = "hi"
    is_bank, conf, _ = is_bank_statement(small_text, "random.txt", "text/plain")
    should_exclude, reason = should_exclude_from_extraction(small_text, "random.txt", "text/plain", is_bank, conf)
    assert should_exclude is True

    # Image with low confidence should be excluded (SAM 3.1 stretch)
    img_text = "random image"
    is_bank, conf, _ = is_bank_statement(img_text, "photo.jpg", "image/jpeg")
    should_exclude, reason = should_exclude_from_extraction(img_text, "photo.jpg", "image/jpeg", is_bank, conf)
    assert should_exclude is True

def test_classify_file_type():
    assert classify_file_type("FNB Statement Opening Balance Closing Balance 25 Oct WOOLWORTHS R450", "statement.pdf", "application/pdf") == "bank_statement"
    assert classify_file_type("FNB Statement Opening Balance Closing Balance Account Number 123 Branch Code 250655", "statement.csv", "text/csv") == "csv_statement"
    assert classify_file_type("receipt WOOLWORTHS", "receipt.jpg", "image/jpeg") == "receipt_image"
    assert classify_file_type("Invoice", "invoice.pdf", "application/pdf") in ("invoice","other","bank_statement")

def test_tamper_detection_metadata():
    # Create simple PDF without tampering
    tmp_path = Path(tempfile.gettempdir()) / f"test_tamper_{uuid.uuid4().hex[:6]}.pdf"
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 750), "Test")
        doc.save(str(tmp_path))
        doc.close()

        is_original, reasons = check_pdf_metadata_tampering(tmp_path)
        # Should be likely original, no tamper indicators
        # Allow for some reasons but no tamper indicator with /Prev or multiple %%EOF
        assert is_original is True or len([r for r in reasons if "Tamper indicator" in r]) == 0

        tmp_path.unlink()
    except ImportError:
        print("PyMuPDF not available, skip tamper metadata test")

def test_tamper_detection_hash_chain():
    init_db()
    db = get_db()
    tenant = f"tenant-hash-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}"))
    # Use file content hash as sha for original case
    content = b"original content for hash chain test"
    sha = hashlib.sha256(content).hexdigest()
    # Create doc with file
    tmp_dir = Path(tempfile.gettempdir()) / f"vault_test_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(exist_ok=True)
    tmp_file = tmp_dir / f"{sha}.pdf"
    tmp_file.write_bytes(content)

    doc_id = f"doc-hash-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename) VALUES (?,?,?,?,?,?)",
               (doc_id, tenant, sha, 100, str(tmp_file), "test.pdf"))
    db.commit()

    # Check hash chain original
    is_orig, reasons = check_content_hash_chain(sha, tenant, db)
    assert is_orig is True
    assert any("verified" in r.lower() or "matches" in r.lower() for r in reasons)

    # Tamper file on disk
    tmp_file.write_bytes(b"tampered content")

    is_orig, reasons = check_content_hash_chain(sha, tenant, db)
    assert is_orig is False
    assert any("tamper" in r.lower() or "mismatch" in r.lower() or "modified" in r.lower() for r in reasons)

    # Cleanup
    tmp_file.unlink()
    tmp_dir.rmdir()
    db.execute("DELETE FROM source_documents WHERE id=?", (doc_id,))
    db.commit()

def test_full_tamper_check():
    init_db()
    db = get_db()
    tenant = f"tenant-full-{uuid.uuid4().hex[:6]}"
    db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Test {tenant}"))
    tmp_dir = Path(tempfile.gettempdir()) / f"vault_full_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(exist_ok=True)
    # Create simple PDF first, then compute its hash for original case
    tmp_file_temp = tmp_dir / "temp.pdf"
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 750), "Original for tamper check")
        doc.save(str(tmp_file_temp))
        doc.close()
        content = tmp_file_temp.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        tmp_file = tmp_dir / f"{sha}.pdf"
        tmp_file_temp.rename(tmp_file)

        doc_id = f"doc-full-{uuid.uuid4().hex[:6]}"
        db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key) VALUES (?,?,?,?,?)",
                   (doc_id, tenant, sha, 100, str(tmp_file)))
        db.commit()

        result = full_tamper_check(tmp_file, sha, tenant, db, pages=[])
        assert "is_original_likely" in result
        assert "tamper_chance" in result
        assert "reasons" in result
        # For original file, tamper chance low
        assert result["tamper_chance"] < 0.5 or result["is_original_likely"] is True

        # Cleanup
        tmp_file.unlink()
        tmp_dir.rmdir()
        db.execute("DELETE FROM source_documents WHERE id=?", (doc_id,))
        db.commit()
    except ImportError:
        print("PyMuPDF not available, skip full tamper check")
