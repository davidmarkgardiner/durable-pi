"""Verify the extracted handoff against its source manifest."""
import hashlib
from pathlib import Path
root = Path(__file__).resolve().parents[1]
rows = (root/'MANIFEST.sha256').read_text().splitlines()
for row in rows:
    digest, name = row.split('  ', 1)
    path = root/name
    if not path.resolve().is_relative_to(root) or not path.is_file(): raise SystemExit('Missing/invalid path: '+name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise SystemExit('Checksum mismatch: '+name)
print('PASS: '+str(len(rows))+' bundled files match their checksums')
