# Native kagent through the Pi hub

This POC reuses the existing Pi network UI. A small adapter converts real native kagent session/task artifacts and its human tool approval into the hub's display protocol. Agent execution stays in the installed kagent and Substrate runtime. The adapter stores observation and dispatch receipts in its own PVC.

The original Lumen Market synthetic checkout generator runs in a Kubernetes sidecar. It executes the upstream checkout code and emits genuine synthetic guest-checkout exceptions after the scheduled bad revision. TypeSafe Jev classifies the rows using the original Choice and Score questions. Code requires three incident judgments with probability at least 0.6 for the same fingerprint before it automatically dispatches a fresh native kagent investigator and reviewer.

The classifier stops paid requests after dispatch and has a hard limit of 48 requests. The native agent model is the existing deterministic scripted comparison service. Its native MCP tools operate on a separate protected synthetic fixture. This proves proactive dispatch, native actors, actual tool artifacts, the shared UI and approval routing. It does not prove autonomous repair of the original checkout source or deployment of its fix. Those need a live reasoning-model route and Kubernetes tools for worktree/tests/rollout.

The retained comparison incident has two roles. Displayed numeric IDs are aliases for the native UUIDs, which remain visible in each transcript binding. Approval calls validate the native task and pending tool, require reviewer PASS, then use the native kagent HITL response and the fixture's independent decision ledger. A blocked publish call is displayed as pending and is never called an executed effect. A completed display requires the native result to match the independent ledger.

The retained incident has no arbitrary-chat controls. The separate Live Kimi chat workspace now has a composer and supported slash commands. Creation, forks, model settings and shared-state editing remain outside this adapter. The existing Pi devices retain those features. The TypeSafe key stays in a Kubernetes Secret and never reaches the hub or browser.

## Live GitLab rollback workflow

The third workspace, **Lumen GitLab rollback**, now uses live native specialist and reviewer agents with real application, GitLab and Flux tools. Three actual synthetic checkout failures were classified by Jev; the specialist opened real MR !1; its exact-head GitLab pipeline succeeded and the native reviewer returned PASS. The human approved the native gate, GitLab merged, Flux applied the matching merge commit and the native agent verified three HTTP 200 checkout responses on v1. Independent completed proof passed. The pane defaults to a concise Workflow results view; original messages and receipts remain available in Full agent transcript.

See [GITLAB-ROLLBACK.md](GITLAB-ROLLBACK.md) for the presenter walkthrough, credentials' expiry dates, evidence and current boundaries. `capture-gitops.py --expect awaiting_approval` verifies the pending gate through independent native, GitLab and Kubernetes reads. After the human decision and recovery, `capture-gitops.py --expect completed` requires actual merge, Flux and native application-verification receipts.

Run `python3 -m unittest discover -s apps/kagent-hub-bridge -p 'test_*.py'` for artifact/approval interpretation checks. `deploy.py` must run in the existing isolated Proxmox lab and creates fresh named resources; it never changes the installed worker or old demo trials. Runtime configuration and tokens belong in private `.data` files.

## Live walkthrough on this Mac

Verified on 14 October 2026. Open http://127.0.0.1:4781/ and select **kagent-proxmox → Proactive checkout incident → Native investigator**. The hub shows three online devices, including the standalone Pi VM and the native Kubernetes POC.

1. Open **Logs**. Jev 1.13.0 judged 12 rows: nine normal and three incident. The incident rows are 10, 11 and 12, all real synthetic checkout TypeErrors. Expand a row for its raw entry, probabilities, impact and usage. Classification paused after dispatch, preserving its 48-request ceiling.
2. Open the **Native read-only reviewer**. Its native tools read the incident and independent operation ledger, then returned PASS for the exact proposal. It cannot record or publish a proposal.
3. Return to **Native investigator**. Its saved read_incident, record_proposal and blocked publish_proposal are visible. The native task now shows the recorded approval and completed independent readback: one decision, one publish attempt and one synthetic effect. The card explains the recorded cause, proposed change, expected result, scope and decision consequences. Decisions must match the displayed task, approval ID and proposal request.
4. The **State** tab exposes the actual actor records. At the latest capture, both completed actors were Suspended with saved snapshots. They are hosted by kagent and Substrate; the bridge is an observer and dispatcher.

The native task is `01a139aa-38a9-7922-9062-5a80c4c97b3b`, its context is `01a139aa-3729-7ebb-9e43-f76f8679a022`, and the proposal SHA-256 is `f56706f45ec8833e90ff7888d2006148997bfe9ceea5b5a4dce97d961b3a2d2f`. The private `.data/live-proof.json` captures independent native controller and fixture readback. `capture.py` can refresh it and checks rejection of wrong-task and non-boolean approval requests without choosing a decision. The original Pi release-check task is separate.

Build/type checks, frontend lint, eighteen interpretation/admission tests and the existing hub integration test passed. Invalid live approval requests returned HTTP 409 without effects. The bridge's anonymous device endpoint returned HTTP 401. Bridge updates retained the same native approval and 12 Jev calls. The recorded human decision has now completed and independently verified one effect.

`build-context.py` packages the unchanged upstream log/application sources and two seed-only adaptations: run tests with Node directly and clear mounted directory contents instead of removing volume mount roots. Deployments use Recreate so only one observer/model-cache process owns each SQLite store during updates. The current lab image is `durable-pi-hub-bridge:20261014-14`. [WORKPLACE-PLAN.md](WORKPLACE-PLAN.md) describes the earlier comparison scope; the new home-lab GitLab workflow is documented separately above.

Skills, Models and Tools now read observed Kubernetes metadata refreshed every minute by `dpi-kagent-capabilities.timer`. The two templates currently declare no skills. The model garden identifies the scripted selected route and configured alternatives; Tools marks native human approval. See [AGENT-WORKSPACE.md](AGENT-WORKSPACE.md) for the specialist/SDLC design, historical work and current durability/compaction boundaries.

## Live native chat

Choose **kagent-proxmox → Live Kimi chat → Live Kimi specialist** or **Live Kimi reviewer** to use the composer. Type `/` for the six supported navigation/help commands. Both agents use live Kimi and read-only incident tools, with a shared eight-request/20,000-token ceiling. See [LIVE-CHAT.md](LIVE-CHAT.md) for protocol, scope and proof.

The original incident now completed its recorded human approval. Its strict revision conversion was repaired, and the same native task independently verified one synthetic effect. The original task and proposal identities remain unchanged.
