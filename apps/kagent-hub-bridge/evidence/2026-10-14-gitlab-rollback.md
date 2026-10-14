# Live GitLab rollback gate, 14 October 2026

## Completed after the human click

At 12:11 UTC, `capture-gitops.py --expect completed` independently passed. The human decision was recorded at 12:07 UTC; MR !1 merged at 12:07:50 with SHA `bbbb59d121eb4cf96cabd95ba4aa716a582fb09a`. Flux applied exactly that SHA, Deployment checkout reached observed generation 3 on v1 with one available replica, and three checkout probes returned HTTP 200/version v1/total 20. Native verification task `01a13a50-73de-7f21-9f82-0b4137096153` completed with the same successful tool receipt. Model usage was 10/24 requests and 41,285 reported tokens, with no reset. Raw completed proof is ignored `.data/gitops-completed-proof.json`.

The following table preserves the earlier gate-stage receipt.

This receipt is for the isolated home-lab cluster `kind-pi-durable-local`, not workplace infrastructure. The synthetic application is real running code; the model, classification requests, native tasks, GitLab MR and CI are live.

| Stage | Observed evidence | State |
| --- | --- | --- |
| Healthy baseline | v1 returned HTTP 200 three times before fault injection | PASS |
| Regression | Flux applied `20f6b6a0cc0229846576fdb97d54cdbbf00f182b`; actual v2 checkout returns HTTP 500 / KeyError loyalty | PASS |
| Classification | Three TypeSafe Jev incident judgments; monitor paused after dispatch | PASS |
| Native investigation | Actual read_incident, read_deployment, read_gitops, create_rollback_mr and inspect_mr artifacts | PASS |
| Real proposal | GitLab MR !1, only deploy/deployment.json image v2 → v1 | PASS |
| Exact-head CI | Pipeline 2946626328 and checkout-tests succeeded at `1cd21e0b2a815f3baa12338bdbaef64aa9523ba2` | PASS |
| Native review | Task `01a13a34-e7c6-75b2-bee9-94174397c250`, inspect_mr receipt, PASS for exact SHA | PASS |
| Human gate | Native task `01a13a34-3b4c-7bf3-b6aa-4f6a8c7a2f72` INPUT_REQUIRED; merge_mr approval `adk-3b6656f5-45d7-4290-873b-5b0a737a9314` | WAITING |
| Merge and recovery | No decision, merge attempt or merged SHA; application remains on v2 | NOT EXECUTED |

MR: https://gitlab.com/davidmarkgardiner/durable-pi-lumen-gitops/-/merge_requests/1

CI: https://gitlab.com/davidmarkgardiner/durable-pi-lumen-gitops/-/pipelines/2946626328

The independent capture reads the native controller directly and separately reads GitLab MR/diff/pipeline/jobs and Kubernetes Deployment/pods. Raw proof is retained in ignored `.data/gitops-awaiting_approval-proof.json`. Model guard: 6/24 provider requests, 18,196 reported tokens, not halted at capture. This allowance has not been reset. The first native task failed at the former gateway request-size ceiling; it is retained in the same context as evidence of the setup correction.

Bridge image: `durable-pi-hub-bridge:20261014-14`. Frontend build and lint pass; 27 adapter/merge-gate/admission tests pass. Local tests do not prove the pending merge path. Post-decision proof requires `capture-gitops.py --expect completed`, including actual native verification and correlated GitLab/Flux/application receipts.

## Visible classifier handoff

The Pi pane now shows three real HTTP 500 responses, TypeSafe Jev judgments, the bridge threshold, exact A2A instruction and original native message/context/task IDs. Admission is confirmed only when GetTask history matches the exact message ID and instruction. The original task retains TASK_STATE_FAILED; the later continuation and final verification remain visible. Browser verification on 14 October confirmed the panel and expanded receipt in the completed workspace. Screenshot: ../.data/classifier-handoff.png.

The portable workplace handoff is work-agent-bundles/remote-kagent-pi-demo. It replaces Jev with a labelled scripted decision, exposes HTTP/SSE from a remote cluster bridge, and preserves native task/MCP/approval semantics. See its VERIFICATION.md for the distinction between checked package/native connectivity and pending workplace end-to-end proof.
