#!/usr/bin/env python3
"""Coordinate an existing investigator/reviewer pair through the local Pi hub."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from handoff_transport import connection


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def verdict(text):
    value = json.loads(text)
    if not isinstance(value, dict) or value.get("verdict") not in {"PASS", "CHANGES_REQUIRED"}:
        raise ValueError("Reviewer must return a JSON verdict: PASS or CHANGES_REQUIRED")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hub", default="http://127.0.0.1:4781")
    parser.add_argument("--backend-env", type=Path, help="Connect directly to the local backend using its existing environment file")
    parser.add_argument("--device", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--investigator", type=int, default=1)
    parser.add_argument("--reviewer", type=int, required=True)
    parser.add_argument("--incident", required=True)
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True, help="Reuse this ID to resume; use a new ID for new work")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".dpi/handoffs")
    parser.add_argument("--timeout", type=int, default=300, help="Maximum seconds per stage")
    parser.add_argument("--stop-after", choices=["investigate", "review"])
    args = parser.parse_args()
    if args.investigator == args.reviewer or args.timeout <= 0:
        parser.error("Use distinct agents and a positive timeout")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.incident):
        parser.error("Incident ID must contain only letters, digits, underscores or hyphens")
    if urllib.parse.urlparse(args.hub).hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("The coordinator connects only to a local hub")
    task = args.task_file.read_text()
    identity = {key: getattr(args, key) for key in ["hub", "device", "session", "investigator", "reviewer", "incident", "run_id"]}
    identity["task_sha256"] = hashlib.sha256(task.encode()).hexdigest()
    if args.backend_env:
        identity["backend_env"] = str(args.backend_env.expanduser().resolve())
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(args.run_id.encode()).hexdigest()[:24]
    path = args.state_dir / (key + ".json")
    lock = (args.state_dir / (key + ".lock")).open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another coordinator is already running this run ID")
    state = json.loads(path.read_text()) if path.exists() else {"identity": identity, "stages": {}}
    if state["identity"] != identity:
        raise SystemExit("Run ID already belongs to different inputs; restore the original inputs or use a new run ID")
    base, headers = connection(args.hub, args.device, identity.get("backend_env"))

    def call(route, body=None):
        request = urllib.request.Request(base + route, data=None if body is None else json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def agent(number):
        return "/sessions/" + urllib.parse.quote(args.session, safe="") + "/agents/" + str(number)

    def check_reviewer():
        detail = call(agent(args.reviewer))
        allowed = {"read", "read_state", "list_durable_jobs", "check_durable_job", "search_history", "handoff"}
        offered = {tool["name"] for tool in detail["tools"] if tool["offered"]}
        if not detail["config"]["readOnly"] or not offered <= allowed:
            raise RuntimeError("Reviewer is not read-only; refusing to hand off")
        state["reviewer_tools"] = sorted(offered)

    check_reviewer()
    save(path, state)

    def stage(name, number, prompt):
        record = state["stages"].get(name)
        if record and record.get("status") == "done":
            print(name + ": restored completed submission " + str(record["submissionId"]), flush=True)
            return record["answer"]["text"]
        if record is None:
            if call(agent(number))["busy"]:
                raise RuntimeError("Agent is busy with other work; retry when idle")
            record = {"prompt": prompt, "requestId": str(uuid.uuid5(uuid.NAMESPACE_URL, args.run_id + ":" + name)), "status": "pending"}
            state["stages"][name] = record
            save(path, state)
        print(name + ": running", flush=True)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            try:
                result = call(agent(number) + "/messages", {"content": record["prompt"], "requestId": record["requestId"], "whenBusy": "reject", "waitMs": 1000})
            except urllib.error.HTTPError as error:
                if error.code not in {502, 503}:
                    raise
                time.sleep(2)
                continue
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2)
                continue
            record.update(result)
            save(path, state)
            if result["status"] == "done":
                print(name + ": completed submission " + str(result["submissionId"]), flush=True)
                return result["answer"]["text"]
            if result["status"] == "unanswered":
                raise RuntimeError(name + " ended without an answer: " + str(result.get("reason")))
            time.sleep(1)
        raise TimeoutError("Stage timed out; rerun the identical command to resume. The agent task remains intact.")

    investigation = stage("investigate", args.investigator, task + "\n\nPrepare a file handoff and evidence for Reviewer. Do not spawn other agents or claim review passed. Do not deploy, approve, or contact external services. The coordinator will deliver your answer to Reviewer.")
    if args.stop_after == "investigate":
        print("Stopped after investigation. Rerun without --stop-after to continue.")
        return
    check_reviewer()
    review = stage("review", args.reviewer, "Independently review the investigator's handoff below. Read the referenced repository files, diff, original evidence and recorded test results using your read-only tools. Do not run shell commands, modify files or App State, approve, or deploy. Distinguish recorded test evidence from tests you executed. Reply with ONLY a JSON object containing verdict (PASS or CHANGES_REQUIRED), findings, evidenceRead, and limitations. PASS covers only this bounded synthetic local fix, never deployment approval.\n\n" + investigation)
    decision = verdict(review)
    state["verdict"] = decision
    save(path, state)
    if args.stop_after == "review":
        print("Stopped after review. Rerun without --stop-after to continue.")
        return
    target_status = "reviewed" if decision["verdict"] == "PASS" else "changes_required"
    stage("record", args.investigator, "Reviewer completed its independent read-only review. Save its verbatim JSON to REVIEW.json. Update only /incidents/" + args.incident + "/status to " + target_status + ", and its review object to include reviewerId=" + str(args.reviewer) + ", runId=" + json.dumps(args.run_id) + ", verdict=" + decision["verdict"] + ", testsExecutedByReviewer=false, deploymentApproved=false, and the supplied findings and limitations. Do not alter the fix or other incident records, start new work, or deploy. Then read the incident back and report the result.\n\n" + review)
    incident = call("/docs/app.shared-state")["value"]["incidents"][args.incident]
    if incident.get("status") != target_status or incident.get("review", {}).get("runId") != args.run_id or incident["review"].get("verdict") != decision["verdict"] or incident["review"].get("deploymentApproved") is not False:
        raise RuntimeError("Final incident readback does not match this run's verdict")
    check_reviewer()
    state["incident"] = incident
    state["completed"] = True
    save(path, state)
    print("Completed: " + decision["verdict"] + "; evidence: " + str(path), flush=True)


if __name__ == "__main__":
    main()
