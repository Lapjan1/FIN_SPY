import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.db import init_db, get_db
from apps.api.reports import generate_powerbi_pack
import uuid

init_db()
db = get_db()
tenant = f"tenant-powerbi-demo-{uuid.uuid4().hex[:6]}"
db.execute("INSERT INTO tenants (id, name) VALUES (?,?)", (tenant, f"Demo {tenant}"))
db.execute("INSERT INTO accounts (id, tenant_id, code, name, type) VALUES (?,?,?,?,?)", (f"acc-{tenant}-1000", tenant, "1000", "Bank", "asset"))
db.execute("INSERT INTO transactions (id, tenant_id, txn_date, description_raw, amount_minor, fingerprint_sha256) VALUES (?,?,?,?,?,?)", (f"txn-{uuid.uuid4().hex[:6]}", tenant, "2026-10-26", "WOOLWORTHS", -45000, "fp1"))
db.execute("INSERT INTO transactions (id, tenant_id, txn_date, description_raw, amount_minor, fingerprint_sha256) VALUES (?,?,?,?,?,?)", (f"txn-{uuid.uuid4().hex[:6]}", tenant, "2026-10-26", "SALARY", 1500000, "fp2"))
import hashlib
sha_rand = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()
db.execute("INSERT INTO source_documents (id, tenant_id, sha256, size_bytes, storage_key, original_filename) VALUES (?,?,?,?,?,?)", (f"doc-{uuid.uuid4().hex[:6]}", tenant, sha_rand, 100, "vault/a.pdf", "statement.pdf"))
db.commit()

pack = generate_powerbi_pack(tenant)
print("PowerBI pack generated:")
print(f"  Excel: {pack['file_key']}")
print(f"  SHA256: {pack['sha256'][:16]}...")
print(f"  CSV dir: {pack['csv_dir']}")
print(f"  Counts: {pack['counts']}")
for csv in pack['csv_keys'][:3]:
    print(f"  CSV: {csv}")

# Cleanup
import shutil
Path(pack["file_key"]).unlink(missing_ok=True)
shutil.rmtree(pack["csv_dir"], ignore_errors=True)
db.execute("DELETE FROM transactions WHERE tenant_id=?", (tenant,))
db.execute("DELETE FROM accounts WHERE tenant_id=?", (tenant,))
db.execute("DELETE FROM source_documents WHERE tenant_id=?", (tenant,))
db.execute("DELETE FROM tenants WHERE id=?", (tenant,))
db.commit()
print("Cleanup done, pack generation works!")

# Also test via API endpoint
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.auth import create_user
import uuid as uuid2

email = f"powerbi_{uuid2.uuid4().hex[:6]}@test.com"
tenant2 = f"tenant-pb-api-{uuid2.uuid4().hex[:6]}"
client = TestClient(app)
client.post('/v1/auth/register', json={'email':email,'password':'pass123','name':'PowerBI','tenant_id':tenant2})
r = client.post('/v1/auth/login', json={'email':email,'password':'pass123'})
uid = r.json()['id']
r = client.get('/v1/reports/powerbi', headers={'X-User-Id': str(uid)})
print(f"\nAPI GET /v1/reports/powerbi status {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  file_key {data['file_key']}")
    print(f"  counts {data['counts']}")
    # Cleanup file
    Path(data['file_key']).unlink(missing_ok=True)
    shutil.rmtree(data['csv_dir'], ignore_errors=True)
    # Cleanup user
    db.execute("DELETE FROM users WHERE email=?", (email,))
    db.execute("DELETE FROM tenants WHERE id=?", (tenant2,))
    db.commit()
    print("API test cleanup done")
else:
    print(r.text)
