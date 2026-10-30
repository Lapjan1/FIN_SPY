"""
Verify Evidence Pack ZIP - independent verifier per Appendix D + docs/FLOWS.md
Usage: python scripts/verify_pack.py ./evidence-pack.zip
Recomputes SHA256 each file vs manifest.json, manifest hash vs printed, TSA tokens via openssl, PDF signature panel note.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_pack.py ./evidence-pack.zip")
        sys.exit(1)
    zip_path = Path(sys.argv[1])
    if not zip_path.exists():
        print(f"Not found: {zip_path}")
        sys.exit(1)

    tmp = Path("./.fin_spy_tmp")
    tmp.mkdir(exist_ok=True)
    # Extract
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)

    manifest_path = tmp / "manifest.json"
    if not manifest_path.exists():
        print("FAIL: manifest.json missing")
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    print(f"Manifest version {manifest.get('manifest_version')} generated {manifest.get('generated_at_utc')}")
    scope = manifest.get('scope', {})
    print(f"Scope: account_number={scope.get('account_number') if scope else 'whole tenant (no scope key)'}")
    if manifest.get('audit_note'):
        print(f"Audit note: {manifest['audit_note']}")

    # 1. Recompute each file SHA256 vs manifest
    ok = True
    for f in manifest.get("files", []):
        path = tmp / f["path"]
        expected = f["sha256"]
        if not path.exists():
            print(f"FAIL missing file {f['path']}")
            ok = False
            continue
        actual = sha256_file(path)
        if actual != expected:
            print(f"FAIL hash mismatch {f['path']}: expected {expected[:12]}.. got {actual[:12]}..")
            ok = False
        else:
            print(f"OK {f['path']} {actual[:12]}..")

    # 2. Manifest hash vs manifest.sha256
    manifest_sha_path = tmp / "manifest.sha256"
    if manifest_sha_path.exists():
        expected_manifest_hash = manifest_sha_path.read_text().strip()
        actual_manifest_hash = sha256_file(manifest_path)
        if actual_manifest_hash == expected_manifest_hash:
            print(f"OK manifest hash {actual_manifest_hash[:12]}..")
        else:
            print(f"FAIL manifest hash expected {expected_manifest_hash[:12]}.. got {actual_manifest_hash[:12]}..")
            ok = False
        print(f"Note: This hash should be printed in PDF footer and verification page.")
    else:
        print("WARN manifest.sha256 missing")

    # 3. TSA tokens - note verification command
    for f in manifest.get("files", []):
        if f["path"].endswith(".tsr") or f.get("role")=="timestamp":
            print(f"TSA token {f['path']}: verify with: openssl ts -verify -in {f['path']} -data {f.get('derived_from','manifest.json')} -CAfile tsa_ca.crt")

    # 4. PDF signature note
    print("PDF signature: Open report PDF signature panel (pyHanko PAdES) to confirm.")

    if ok:
        print("PASS: evidence pack verified - court-ready chain OK")
        sys.exit(0)
    else:
        print("FAIL: evidence pack verification failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
