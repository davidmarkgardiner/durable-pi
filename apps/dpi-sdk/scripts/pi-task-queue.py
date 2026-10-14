#!/usr/bin/env python3
"""Persistent, serial queue for a configured Pi investigator/reviewer pair."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from queue_worktree import freeze, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home() / ".dpi/task-queue")
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("--id", required=True)
    submit.add_argument("--task-file", required=True, help="UTF-8 file, or - for stdin")
    commands.add_parser("status")
    retry = commands.add_parser("retry")
    retry.add_argument("id")
    commands.add_parser("worker")
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (home / "initialize.lock").open("a") as initialize_lock:
        fcntl.flock(initialize_lock, fcntl.LOCK_EX)
        db = sqlite3.connect(home / "queue.sqlite", timeout=10, isolation_level=None)
        if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
            db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS jobs (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','done','failed')), attempts INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, started REAL, finished REAL, error TEXT)")
    if args.command == "status":
        rows = [dict(zip(["id", "status", "attempts", "created", "started", "finished", "error"], row)) for row in db.execute("SELECT id,status,attempts,created,started,finished,error FROM jobs ORDER BY seq")]
        for row in rows:
            receipts = list((home / "jobs" / row["id"] / "progress").glob("*.json"))
            if receipts:
                row["verdict"] = json.loads(receipts[0].read_text()).get("verdict", {}).get("verdict")
            resources = home / "jobs" / row["id"] / "resources.json"
            if resources.exists():
                details = json.loads(resources.read_text())
                row.update({key: details[key] for key in ["worktree", "branch", "session", "incident"]})
        print(json.dumps(rows, indent=2))
        return
    if args.command == "submit":
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.id):
            parser.error("Job ID must contain only letters, digits, underscores or hyphens")
        task = sys.stdin.read() if args.task_file == "-" else Path(args.task_file).read_text()
        if not task.strip() or len(task) > 60000:
            parser.error("Task must contain 1 to 60000 characters")
        config = freeze(json.loads((home / "target.json").read_text()))
        payload = json.dumps({"target": config, "task": task}, sort_keys=True)
        db.execute("BEGIN IMMEDIATE")
        try:
            existing = db.execute("SELECT payload,status FROM jobs WHERE id=?", (args.id,)).fetchone()
            if existing:
                if existing[0] != payload:
                    raise ValueError("Job ID already belongs to different inputs")
                status = existing[1]
            else:
                db.execute("INSERT INTO jobs(id,payload,status,created) VALUES(?,?,'queued',?)", (args.id, payload, time.time()))
                status = "queued"
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        print(json.dumps({"id": args.id, "status": status}))
        return
    if args.command == "retry":
        changed = db.execute("UPDATE jobs SET status='queued',error=NULL,finished=NULL WHERE id=? AND status='failed'", (args.id,)).rowcount
        if not changed:
            raise SystemExit("Retry accepts only an existing failed job")
        print(json.dumps({"id": args.id, "status": "queued"}))
        return

    lock = (home / "worker.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Another queue worker is already running")
    # Owning the worker lock proves no prior worker is still processing a job.
    db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
    print("Queue worker ready", flush=True)
    while True:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT id,payload FROM jobs WHERE status='queued' ORDER BY seq LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE jobs SET status='running',attempts=attempts+1,started=?,error=NULL WHERE id=?", (time.time(), row[0]))
        db.execute("COMMIT")
        if not row:
            time.sleep(1)
            continue
        job_id, payload = row
        directory = home / "jobs" / job_id
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        task_file = directory / "task.txt"
        target = json.loads(payload)["target"]
        print("Starting " + job_id, flush=True)
        try:
            target = prepare(target, job_id, directory)
            task = json.loads(payload)["task"]
            for key, value in {"INCIDENT_ID": target["incident"], "WORKTREE": target.get("worktree", ""), "BRANCH": target.get("branch", "")}.items():
                task = task.replace("{{" + key + "}}", value)
            task_file.write_text(task)
            task_file.chmod(0o600)
            command = [sys.executable, str(Path(__file__).with_name("two-agent-handoff.py")), "--hub", target["backend"], "--backend-env", target["backend_env"], "--device", target["device"], "--session", target["session"], "--investigator", str(target["investigator"]), "--reviewer", str(target["reviewer"]), "--incident", target["incident"], "--task-file", str(task_file), "--run-id", "queue-" + job_id, "--state-dir", str(directory / "progress")]
            with (directory / "coordinator.log").open("a") as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=1000)
            status = "done" if result.returncode == 0 else "failed"
            error = None if status == "done" else "Coordinator exited " + str(result.returncode) + "; inspect jobs/" + job_id + "/coordinator.log"
        except Exception as exception:
            status, error = "failed", type(exception).__name__ + ": " + str(exception)
        db.execute("UPDATE jobs SET status=?,finished=?,error=? WHERE id=?", (status, time.time(), error, job_id))
        print(job_id + ": " + status, flush=True)


if __name__ == "__main__":
    main()
