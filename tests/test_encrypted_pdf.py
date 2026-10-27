"""
Test encrypted/password protected PDF handling - intake + extraction
Per user question: can we open if encrypted? password protected?
"""
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.db import init_db, get_db
import uuid

def create_encrypted_pdf(path: Path, password: str = "test123"):
    """Create a simple encrypted PDF using PyMuPDF for testing"""
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "25 Oct 2026 WOOLWORTHS R450,00 R12 340,55")
        # Encrypt with password
        # 4 = 128-bit encryption, owner password same as user for simplicity
        doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_128, user_pw=password, owner_pw=password)
        doc.close()
        return True
    except Exception as e:
        print(f"Failed to create encrypted PDF via PyMuPDF: {e}, trying reportlab")
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            c = canvas.Canvas(str(path), pagesize=letter)
            c.drawString(100, 750, "25 Oct 2026 WOOLWORTHS R450,00 R12 340,55")
            c.save()
            # Reportlab doesn't encrypt easily, so we skip encryption for fallback
            return False
        except Exception as e2:
            print(f"Both failed: {e2}")
            return False

def setup_user():
    init_db()
    email = f"enc_{uuid.uuid4().hex[:8]}@test.com"
    tenant = f"tenant-enc-{uuid.uuid4().hex[:8]}"
    client = TestClient(app)
    client.post('/v1/auth/register', json={'email':email,'password':'pass123','name':'Enc','tenant_id':tenant})
    r = client.post('/v1/auth/login', json={'email':email,'password':'pass123'})
    uid = r.json()['id']
    return client, uid, tenant

def test_encrypted_pdf_detection():
    """Test that encrypted PDF is detected as is_encrypted"""
    tmp_path = Path(f"/tmp/test_enc_{uuid.uuid4().hex[:6]}.pdf")
    created = create_encrypted_pdf(tmp_path, "test123")
    if not created:
        print("Skipping encrypted detection test - PyMuPDF encryption not available")
        return
    # Check detection via fitz
    import fitz
    doc = fitz.open(str(tmp_path))
    assert doc.is_encrypted is True
    assert doc.needs_pass is True
    # Try without password - should fail or needs_pass
    doc.close()
    # Try with correct password
    doc = fitz.open(str(tmp_path))
    auth = doc.authenticate("test123")
    assert auth != 0, "Correct password should authenticate"
    doc.close()
    # Try with wrong password
    doc = fitz.open(str(tmp_path))
    auth = doc.authenticate("wrongpass")
    assert auth == 0, "Wrong password should fail auth"
    doc.close()
    tmp_path.unlink()

def test_upload_encrypted_pdf_without_password():
    """Upload encrypted PDF without password should return status needs_password"""
    tmp_path = Path(f"/tmp/test_enc_upload_{uuid.uuid4().hex[:6]}.pdf")
    created = create_encrypted_pdf(tmp_path, "test123")
    if not created:
        print("Skipping - encryption not available")
        return
    client, uid, tenant = setup_user()
    with tmp_path.open("rb") as f:
        files = {'file': ('encrypted.pdf', f, 'application/pdf')}
        r = client.post('/v1/documents', headers={'X-User-Id': str(uid)}, files=files)
    assert r.status_code == 200
    data = r.json()
    assert data.get('is_encrypted') is True
    assert data.get('status') == "needs_password"
    tmp_path.unlink()

def test_upload_encrypted_pdf_with_correct_password():
    """Upload encrypted PDF with correct password should return queued"""
    tmp_path = Path(f"/tmp/test_enc_correct_{uuid.uuid4().hex[:6]}.pdf")
    created = create_encrypted_pdf(tmp_path, "test123")
    if not created:
        print("Skipping - encryption not available")
        return
    client, uid, tenant = setup_user()
    with tmp_path.open("rb") as f:
        files = {'file': ('encrypted.pdf', f, 'application/pdf')}
        # Provide password via form field pdf_password
        r = client.post('/v1/documents', headers={'X-User-Id': str(uid)}, files=files, data={'pdf_password': 'test123'})
    assert r.status_code == 200
    data = r.json()
    assert data.get('is_encrypted') is True
    # With correct password, status should be queued (decrypted)
    assert data.get('status') == "queued"
    tmp_path.unlink()

def test_upload_encrypted_pdf_with_wrong_password():
    """Upload encrypted PDF with wrong password should return needs_password"""
    tmp_path = Path(f"/tmp/test_enc_wrong_{uuid.uuid4().hex[:6]}.pdf")
    created = create_encrypted_pdf(tmp_path, "test123")
    if not created:
        print("Skipping - encryption not available")
        return
    client, uid, tenant = setup_user()
    with tmp_path.open("rb") as f:
        files = {'file': ('encrypted.pdf', f, 'application/pdf')}
        r = client.post('/v1/documents', headers={'X-User-Id': str(uid)}, files=files, data={'pdf_password': 'wrongpass'})
    assert r.status_code == 200
    data = r.json()
    assert data.get('is_encrypted') is True
    assert data.get('status') == "needs_password"
    tmp_path.unlink()

def test_extraction_encrypted_with_password():
    """Test extractor can open encrypted PDF with password"""
    tmp_path = Path(f"/tmp/test_enc_extract_{uuid.uuid4().hex[:6]}.pdf")
    created = create_encrypted_pdf(tmp_path, "test123")
    if not created:
        print("Skipping - encryption not available")
        return
    from apps.worker.parsers.extractor import extract_text_with_bbox
    # Without password should raise ValueError needs_password
    try:
        pages = extract_text_with_bbox(tmp_path, password=None)
        assert False, "Should have raised ValueError for encrypted PDF without password"
    except ValueError as e:
        assert "needs_password" in str(e) or "encrypted" in str(e).lower()
    # With correct password should succeed
    pages = extract_text_with_bbox(tmp_path, password="test123")
    assert len(pages) >= 1
    assert len(pages[0]['lines']) >= 1
    tmp_path.unlink()

def test_password_not_logged_or_stored():
    """Ensure password not stored in DB or logs per AGENTS.md Never print secrets"""
    tmp_path = Path(f"/tmp/test_enc_nolog_{uuid.uuid4().hex[:6]}.pdf")
    created = create_encrypted_pdf(tmp_path, "supersecret123")
    if not created:
        print("Skipping - encryption not available")
        return
    client, uid, tenant = setup_user()
    db = get_db()
    with tmp_path.open("rb") as f:
        files = {'file': ('encrypted.pdf', f, 'application/pdf')}
        r = client.post('/v1/documents', headers={'X-User-Id': str(uid)}, files=files, data={'pdf_password': 'supersecret123'})
    assert r.status_code == 200
    # Check DB does NOT contain password
    cur = db.execute("SELECT * FROM source_documents WHERE tenant_id=?", (tenant,))
    rows = cur.fetchall()
    assert len(rows) >= 1
    # Convert row to dict and check no password field contains our secret
    for row in rows:
        d = dict(row) if not isinstance(row, dict) else row
        # Ensure no column contains password
        for k, v in d.items():
            if isinstance(v, str):
                assert "supersecret123" not in v, f"Password leaked in DB column {k}"
    # Check audit_log does not contain password
    cur = db.execute("SELECT payload_json FROM audit_log WHERE tenant_id=? ORDER BY id DESC LIMIT 5", (tenant,))
    for row in cur.fetchall():
        payload = row["payload_json"] if isinstance(row, dict) else row[0]
        assert "supersecret123" not in payload, "Password leaked in audit_log"
    tmp_path.unlink()
