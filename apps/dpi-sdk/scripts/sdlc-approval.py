#!/usr/bin/env python3
"""Start the synthetic release-note approval gate after a successful team run."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
from handoff_transport import connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    run = json.loads(args.receipt.read_text())
    if not run.get("completed") or run["verdict"]["verdict"] != "PASS":
        raise SystemExit("The completed coordinator receipt must contain PASS")
    identity = run["identity"]
    if urllib.parse.urlparse(identity["hub"]).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Approval gate connects only to a local hub")
    base, headers = connection(identity["hub"], identity["device"], identity.get("backend_env"))
    agent = "/sessions/" + urllib.parse.quote(identity["session"], safe="") + "/agents/" + str(identity["investigator"])

    def call(path, body=None):
        request = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    incident = call("/docs/app.shared-state")["value"]["incidents"][identity["incident"]]
    if incident.get("review", {}).get("runId") != identity["run_id"] or incident["review"].get("verdict") != "PASS":
        raise SystemExit("Current incident review does not match this passing run")
    request_id = "sdlc-approval-" + hashlib.sha256(identity["run_id"].encode()).hexdigest()[:32]
    prompt = "For reviewed synthetic incident " + identity["incident"] + ", start the built-in release-check job with commits=1 and wait=false. This authorizes its built-in read-only gathering subagent. Do not approve or decline it, deploy, merge, modify the fix, or start additional jobs. Its approval only saves synthetic review notes to App State. Report the task ID."
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = call(agent + "/messages", {"content": prompt, "requestId": request_id, "waitMs": 1000, "whenBusy": "reject"})
        if result["status"] == "unanswered":
            raise SystemExit("Approval gate submission ended unanswered")
        if result["status"] == "done":
            break
        time.sleep(1)
    else:
        raise SystemExit("Submission still active; rerun the same command to continue")
    while time.monotonic() < deadline:
        jobs = call(agent + "/docs/demo.job-runs")["value"]["items"]
        candidates = [job for job in jobs.values() if job["job"] == "release-check"]
        if len(candidates) != 1:
            raise SystemExit("Expected exactly one release-check job in this fresh SDLC session")
        job = candidates[0]
        if job.get("approval") in {"pending", "approved", "declined"}:
            receipt = {"incidentId": identity["incident"], "runId": identity["run_id"], "submission": result, "job": job, "scope": "Synthetic release-note approval; no merge or deployment"}
            output = args.receipt.with_name(args.receipt.stem + "-approval.json")
            temporary = output.with_suffix(".tmp")
            temporary.write_text(json.dumps(receipt, indent=2) + "\n")
            temporary.chmod(0o600)
            temporary.replace(output)
            print("Approval task #" + str(job["id"]) + ": " + job["approval"] + "; receipt: " + str(output))
            return
        if job["status"] in {"failed", "aborted"}:
            raise SystemExit("Release-note gate failed: " + str(job.get("error")))
        time.sleep(1)
    raise SystemExit("Gate is still gathering; rerun the same command to continue")


if __name__ == "__main__":
    main()
