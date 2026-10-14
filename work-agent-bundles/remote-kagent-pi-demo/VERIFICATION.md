# Package verification on 14 October 2026

## Verified before handoff

- Portable Python source compiles. A collector smoke check preserved the discovered tool approval flag and selected model metadata. Live workplace inventory remains pending.
- Nine portable behavior checks passed. They cover guest/loyalty behavior, the deliberate v2 failure, labelled scripted classification, exact native handoff correlation, one-time preconditioned fault writes, uncertain-write rejection, and exact live merge approval gates.
- The existing adapter's 28 critical native/task/approval checks passed separately.
- A clean npm ci for both bundled SDK and playground passed. The bundled UI typecheck and production build passed; lint passed.
- The standalone runtime Docker image built on Linux using python:3.12.12-slim-bookworm, pinned Python dependencies and compiled vendored protobuf definitions.
- That built runtime client reached a real remote home-lab native controller through a loopback port-forward. GetVersion returned kagent 1.0.0-alpha11, gitCommit 30e8a2c. GetTask returned the existing completed post-recovery task and matching native context. This read-only canary made zero model calls.
- The bundled preflight/renderer ran against existing home-lab metadata without reading Secret values. Fresh AgentTemplate, Harness, Agent and RemoteMCPServer documents passed Kubernetes server dry-run. No new demo resources were created by this validation.
- The bundled repository generator ran guest/loyalty/regression tests and a real kubectl kustomize render. It made no GitLab write.
- The home-lab Pi pane visibly shows application responses, Jev decisions, the bridge threshold, exact A2A instruction and matching native delivery IDs. It retains the initial provider failure and the successful continuation instead of hiding them.

The original home-lab GitLab rollback previously completed with real native MCP calls, independent review, human approval, merged commit, matching Flux revision and healthy checkout probes. The portable package derives from that adapter, adds a scripted classifier and parameterizes workplace scope.

## Still pending on the workplace target

All workplace connection, model/Secret/registry/CI/mesh/readiness checks and the full scripted-decision-to-real-MR demonstration. No workplace endpoint was contacted. No workplace repository, Secret, namespace or ingress route was changed.

The portable package has not itself completed a new live rollback run. Its built native connection and schema/seed checks are verified; the real approval/merge/recovery checkpoint must be captured on the approved target. Use CHECKPOINTS.md and scripts/verify.py to distinguish generated configuration from actual proof.
