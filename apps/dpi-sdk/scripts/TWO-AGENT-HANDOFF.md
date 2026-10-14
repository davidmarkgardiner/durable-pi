# Coordinate an investigator and reviewer

`two-agent-handoff.py` sends work to two existing agents through a local Durable Pi hub. It requires Python 3 on macOS or Linux and uses only the standard library.

## Run

Create a session containing a writable investigator and a reviewer configured with `readOnly: true`. Put the investigation instructions in a UTF-8 task file. The instructions must prepare a file handoff and create an incident record under `/incidents/<incident-id>` in App State.

```sh
python3 apps/dpi-sdk/scripts/two-agent-handoff.py \
  --device proxmox \
  --session SESSION_ID \
  --investigator 1 \
  --reviewer REVIEWER_ID \
  --incident INC-DEMO-106 \
  --task-file /absolute/path/to/task.txt \
  --run-id incident-review-001
```

Replace `SESSION_ID` and `REVIEWER_ID` with the IDs returned by the backend. Use a new run ID for new work. Reuse the identical command and inputs to resume interrupted work.

## Sequence

1. Verify the reviewer's offered tools and read-only configuration.
2. Submit the task to the investigator and wait for its answer.
3. Send that answer to the reviewer, which reads the referenced evidence and returns a JSON verdict.
4. Return `PASS` or `CHANGES_REQUIRED` to the investigator for recording.
5. Read App State back and check this run's incident status and review metadata.

The reviewer does not execute tests. It reads recorded results and source files. A passing review does not authorize deployment. A `CHANGES_REQUIRED` result is recorded and stops the sequence; it does not start an unrestricted repair loop.

## Resume and evidence

The coordinator writes private JSON receipts under `~/.dpi/handoffs/`. It saves each prompt before submission and assigns a stable request ID to each stage. After a coordinator restart, completed stages are restored from the receipt; interrupted stages resubmit the same request ID so the backend returns the existing submission.

An exclusive file lock prevents two local coordinators from using the same run ID simultaneously. Changed inputs with an existing run ID are rejected. Use `--stop-after investigate` or `--stop-after review` to demonstrate continuation between stages. Remove that option when resuming.

The default deadline is five minutes per stage. A timeout leaves the backend submission intact. Connection errors are retried within that deadline. Resume does not cancel unrelated agent work.

This is a client-side coordinator, not a Pi durable task definition. Its receipts live on the machine running it; agent execution lives in the backend's storage. Losing either store is outside this resume guarantee. The lock does not coordinate multiple client machines or different run IDs. Run one coordinator per agent pair at a time.

Read-only mode removes write-capable tools; it is not a separate operating-system sandbox. This coordinator intentionally uses a loopback hub and never reads provider credentials or device tokens.

## Synthetic SDLC approval gate

For a fresh session with one completed passing team run, start the demo's release-note approval job:

```sh
python3 apps/dpi-sdk/scripts/sdlc-approval.py --receipt /absolute/path/to/coordinator-receipt.json
```

The helper checks that the current incident review matches the receipt's run ID, submits one stable request to the investigator, and waits for the release-check approval. Repeating the same command recovers the existing submission. It requires exactly one release-check job in that session and saves an approval receipt beside the coordinator receipt.

The job uses the demo's built-in gathering subagent, then waits for a human decision. Approval saves synthetic notes to shared App State; it does not merge or deploy. A task file can require `PLAN.md` before implementation and evidence for tests and review. Those files provide an SDLC demonstration, not Git-provider or CI integration.

## Run on the backend VM

Copy `two-agent-handoff.py`, `sdlc-approval.py`, and `handoff_transport.py` together onto the VM. For the coordinator, use `--hub http://127.0.0.1:4780 --backend-env /home/david/.dpi/backend.env` with the same device, session, agent and incident arguments. The endpoint is the local backend in this mode, despite the flag's name. The helper reads the existing device token from that local file; it never reads model OAuth files or stores tokens in receipts.

Run the command through a systemd service to detach it from SSH. Set `User`, `HOME`, `WorkingDirectory`, and a restrictive `UMask` for the intended backend account. Keep the run ID and inputs stable when restarting the service. Give a moved run a new ID because its endpoint and input identity differ from the Mac run. Completed runs restore their existing stage receipts instead of starting model work again.

The approval helper also accepts receipts from direct-backend runs. Persistent progress now lives on the VM alongside the coordinator. No Mac hub, SSH tunnel or browser connection is needed for handoffs. The VM must remain running, the backend must be available, and the VM's model login must remain valid. This removes Mac dependency; it does not establish recovery from VM or Proxmox host loss.
