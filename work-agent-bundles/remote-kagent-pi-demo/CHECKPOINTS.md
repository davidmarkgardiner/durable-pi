# Live acceptance checkpoints

Record status, time, command/result and exact IDs in a private evidence directory. A generated manifest or source test is not live proof. Do not paste Secret values into the record. If a checkpoint fails, retain its literal failure and continue independent work only.

| Checkpoint | Required evidence | Stop condition |
| --- | --- | --- |
| Target discovery | Exact approved kube context, cluster, native controller GetVersion, served CRDs, ready seed Agent/Harness and approved ModelConfig | 0.x/API mismatch, wrong context or missing runtime |
| Model route | Existing approval and enforced allowance, usable model/tool-call route; record actual allowance and usage without reset | Discovery-only evidence or missing tool/model compatibility |
| Local artifact | Portable tests, runtime image build, UI npm ci/build, seed tests and Kustomize output | Failed build or missing dependency/image access |
| Scoped install | Reviewed fresh resource names, native server dry-run, dedicated empty project match, seeded SHA, referenced workplace Secrets, ready agents/pods/Flux | Existing resource collision or broad/unapproved scope |
| HTTP connection | Workstation hub and remote bridge are different hosts; authenticated API and SSE work through the selected forward/route; reconnect retains identities | Endpoint only configurable, stale panel or lost state |
| Baseline | Live healthy image, observed deployment generation, Flux source/applied revision, three actual checkout HTTP 200 responses | Already faulty or Git/cluster drift |
| Fault and classification | Human Start action, actual fault commit, v2 live, three real v2 HTTP 500 responses, synthetic=true decisions and scripted source label | Scripted/replayed HTTP evidence, no actual faulty image |
| Native admission | Exact sent instruction/message ID, context ID and GetTask history match | Unconfirmed admission or model task failure |
| Investigation and proposal | Native task artifacts contain actual read_incident/read_deployment/read_gitops and create_rollback_mr receipts; real MR URL and exact head/base binding | Narration without actual tool receipt |
| Independent review | Read-only native reviewer completed; inspect_mr receipt confirms exact binding, one image-only diff and successful checkout-tests head pipeline | Missing, pending, stale, skipped or different-head CI |
| Human pause | Investigator GetTask INPUT_REQUIRED, native merge_mr approval ID and exact args; MR still open; no decision/merge ledger; matching Pi approval card | Fake approval button, merge before human click or unclear effect |
| Merge | Human click, matching native approval extension, independent live decision ledger and GitLab merged SHA | Agent-submitted approval, expired/changed binding or uncertain merge |
| Recovery | Merge SHA equals both Flux source/applied revisions; healthy deployment image/generation and one updated/available replica; three HTTP 200 v1 responses with total 20; completed native final verify_application receipt | Controller observer alone, stale rollout, missing native result or any mismatched SHA |

scripts/verify.py covers controller receipts, labelled trigger, reviewer/current-head gates, pending native approval and completed recovery. Its connected mode proves version and two contexts only; it is not an application-health or model-invocation proof. Manually inspect actual MCP receipts and rendered UI at the corresponding checkpoints. The tool inventory is rendered configuration until discovery and actual task calls confirm it.

Capture the awaiting_approval receipt before the human click, then the completed receipt afterward. Preserve the MR/pipeline links, full head/merge SHAs and screenshot. Do not use a completed screenshot as evidence of a historical native pause without the saved pending receipt.

## Failure handling

- A GitLab write timeout can mean the write happened. Inspect the exact branch/MR/main commit before retrying. starting or merge_attempted means no automatic repeat.
- A failed native task is retained. The starter does not create a second incident automatically. Report the native error; do not claim the rest of the workflow happened.
- A new MR head/base, failed CI or reviewer FAIL invalidates the demonstration gate. This bundle does not silently rebase and transfer approval to another head.
- Keep the same bridge/tools PVCs on restart. Deleting them removes decision and admission evidence.
- Native snapshot resumption and compaction require target-specific tests. Existing Harness configuration alone does not prove them.
- A fresh repeat needs a new approved run ID, app namespace and dedicated repository scope, or an independently reviewed repeat protocol. Never clear the ledger to obtain another merge.
