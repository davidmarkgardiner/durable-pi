#!/usr/bin/env python3
"""Wait for the local authenticated Pi API before starting its queue worker."""
import argparse
import time
import urllib.error
import urllib.request
from pathlib import Path
from handoff_transport import connection

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--backend", default="http://127.0.0.1:4780")
parser.add_argument("--backend-env", type=Path, required=True)
parser.add_argument("--timeout", type=float, default=30)
args = parser.parse_args()
if args.timeout <= 0:
    parser.error("Timeout must be positive")
base, headers = connection(args.backend, "proxmox", args.backend_env)
deadline = time.monotonic() + args.timeout
while time.monotonic() < deadline:
    try:
        request = urllib.request.Request(base + "/device", headers=headers)
        with urllib.request.urlopen(request, timeout=min(2, max(0.1, deadline - time.monotonic()))) as response:
            response.read()
        print("Pi backend ready", flush=True)
        break
    except urllib.error.HTTPError as error:
        if error.code not in {502, 503}:
            raise SystemExit("Backend readiness failed: HTTP " + str(error.code))
    except (urllib.error.URLError, TimeoutError):
        pass
    time.sleep(min(0.5, max(0, deadline - time.monotonic())))
else:
    raise SystemExit("Pi backend did not become ready before the deadline")
