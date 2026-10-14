# Persistent Pi task queue

`pi-task-queue.py` stores submitted work in SQLite and runs one coordinator at a time. Deploy it beside `two-agent-handoff.py`, `handoff_transport.py`, and `queue_worktree.py` on the backend VM.

Create a private `~/.dpi/task-queue/target.json` with these fields:

```json
{
  "backend": "http://127.0.0.1:4780",
  "backend_env": "/home/david/.dpi/backend.env",
  "device": "proxmox",
  "session": "SESSION_ID",
  "investigator": 1,
  "reviewer": 9,
  "incident": "INC-DEMO-106"
}
```

This target names an existing agent pair and one incident record. Previously submitted jobs retain this mode even when the default target changes.

## Separate resources for new jobs

To allocate an independent worktree, session and agent pair per job, configure the target this way instead:

```json
{
  "backend": "http://127.0.0.1:4780",
  "backend_env": "/home/david/.dpi/backend.env",
  "device": "proxmox",
  "repo": "/home/david/dpi-work/investigator-reviewer-demo",
  "base_ref": "HEAD",
  "worktree_root": "/home/david/dpi-work/queue-worktrees",
  "model": {"provider": "openai-codex", "modelId": "gpt-6.1-sol"}
}
```

Submission pins `base_ref` to its current commit. Worktrees start from that committed tree; uncommitted files in the source checkout are not copied. The worker creates `queue/<job-id>`, a `Queue · <job-id>` session and its investigator and read-only reviewer. Each uses App State `/incidents/job-<job-id>`.

Task templates support `{{INCIDENT_ID}}`, `{{WORKTREE}}` and `{{BRANCH}}`. The task must create its assigned incident record and supply review evidence. Queue status reports the allocated branch, path, session and incident ID. `jobs/<id>/resources.json` retains the resource manifest. Retry reuses the worktree and session, finding an already-created session by its exact name and checking its working directory. Ambiguous or mismatched resources fail rather than choosing another job's resources.

Worktrees and sessions remain available after completion. This queue never deletes or merges them. Different checkouts share Git object storage, but their files, conversations and incident result keys are separate. The worker remains serial. This is file separation, not an operating-system sandbox or permission boundary.

```sh
python3 pi-task-queue.py submit --id example-001 --task-file task.txt
python3 pi-task-queue.py status
python3 pi-task-queue.py retry example-001
python3 pi-task-queue.py worker
```

Run the worker as the backend account through systemd, with `HOME` set, `UMask=0077`, and `KillMode=control-group`. One worker owns a file lock. On restart it requeues unfinished processing and invokes the coordinator with the same run ID and saved progress. The backend's request IDs prevent duplicate submissions. SQLite uses WAL and `synchronous=FULL`; this does not constitute host-loss recovery proof.

The oldest queued job runs first. The worker records attempts, timestamps and failures. Each job has its own task file, append-only coordinator log and progress receipts under `jobs/<id>/`. A repeated ID with identical inputs returns the existing job. Changed inputs with the same ID are rejected.

Only failed jobs can be explicitly retried. A finished coordinator is marked `done` whether its review verdict is `PASS` or `CHANGES_REQUIRED`; the receipt contains the verdict. Failures do not trigger unrestricted repair or repeated paid work. Do not start another coordinator against the same agent pair while the worker is active. This queue does not create sessions, poll issues, merge or deploy.

## Backend readiness at worker startup

A systemd `After` relationship orders service startup but does not confirm the HTTP API is listening. Deploy `wait-backend.py` beside `handoff_transport.py` and add this worker service setting:

```ini
[Service]
ExecStartPre=/usr/bin/python3 /home/david/.dpi/coordinator/wait-backend.py --backend-env /home/david/.dpi/backend.env --timeout 30
```

The check uses the existing local device token to poll `/v1/device`; it does not print the token. Transient connection failures and HTTP 502/503 are retried within the deadline. Other HTTP failures stop startup. On the demo VM, the worker Requires the backend and also restarts when the backend is restarted. A failed queue job still needs explicit retry; installing readiness does not retroactively requeue failures.
