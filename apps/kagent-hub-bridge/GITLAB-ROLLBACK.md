# Lumen GitLab rollback demonstration

Open http://127.0.0.1:4781/ and select **kagent-proxmox → Lumen GitLab rollback → Checkout specialist**.

The specialist now opens in **Workflow results**. This view formats the recorded finding, remediation, review and workflow stages. The final report is the agent's actual text. Expand **MCP tool results** to read individual inputs and formatted receipts, or select **Full agent transcript** for the original prompts, messages and setup failure. Presentation changes do not alter native evidence or approval bindings.

## What happens

1. Flux deploys `lumen-checkout:v2` from the dedicated private GitLab repository. The synthetic guest checkout actually throws `KeyError: loyalty` and returns HTTP 500. `/healthz` still returns 200; pod readiness alone would miss this failure.
2. The monitor probes checkout. TypeSafe `jev-latest` classifies three failures as incidents and the Pi bridge automatically submits a native kagent task.
3. The live Kimi specialist calls MCP tools to read pod logs, the deployment image and the GitLab manifest. It opens a real MR changing only `deploy/deployment.json` from image v2 to v1.
4. GitLab runs `checkout-tests`: guest and loyalty checkout, reproduction of the v2 regression, and manifest checks. The bridge starts the separate native reviewer once the exact-head pipeline succeeds.
5. The reviewer independently calls `inspect_mr`. Its native task must finish with PASS for that head SHA, and its tool receipt must confirm the exact diff and CI. The tool service rechecks those facts before recording the review.
6. The specialist's `merge_mr` call pauses at kagent's native tool approval. The pane displays the cause, image change, scope, MR link, CI link and exact SHA. **The human clicks Approve & merge MR** or rejects it.
7. Approval records the displayed binding in the independent tool-service ledger and resumes that same native tool call. GitLab merges with a SHA precondition. The model cannot issue the ledger authorization.
8. Flux reconciles main. The native specialist checks the application again. Completion requires the actual merged SHA to match Flux's applied revision, deployment image v1 with its observed generation available, and three HTTP 200 checkout responses with version v1 and total 20. The pane only reports completed after a native verification tool receipt confirms this.

## Live identities

- Cluster: `kind-pi-durable-local`, inside the Proxmox Pi VM. The older `proxmox-k8s` SDLC cluster was inspected for context and credentials; this demo is installed in the Pi cluster.
- Application namespace: `lumen-gitops`; Deployment/Service `checkout`.
- Flux v2.9.6: source and kustomize controllers in `flux-lumen`, GitRepository/Kustomization `lumen`; reconciliation every 15 seconds.
- Tools: `lumen-tools` in `kagent`. Its ServiceAccount only reads the checkout deployment, pods/logs and the named Flux resources. It cannot patch the application.
- GitLab: https://gitlab.com/davidmarkgardiner/durable-pi-lumen-gitops
- Native workspace: `native-gitops-591204cf`.
- Specialist: `native-gitops-591204cf-investigator`; context `01a13a2e-5372-7856-8ec6-bd0f15481e1b`.
- Reviewer: `native-gitops-591204cf-reviewer`; context `01a13a2e-5387-7548-8801-3ac8f7938509`.
- MR !1: https://gitlab.com/davidmarkgardiner/durable-pi-lumen-gitops/-/merge_requests/1
- MR head: `1cd21e0b2a815f3baa12338bdbaef64aa9523ba2`.
- Successful head pipeline: https://gitlab.com/davidmarkgardiner/durable-pi-lumen-gitops/-/pipelines/2946626328

## Presenter walkthrough

Show **Logs** for the three Jev judgments. Show **Tools** for read tools, MR creation and the approval-required merge tool. Select **Rollback reviewer** to show its actual MCP result and PASS. Return to **Checkout specialist** and scroll to the workflow card. Review the MR and CI links, then make the human decision in the pane. Watch the last two stages and the resulting verification receipt. Do not label the application fixed while the card is still waiting or Flux is reconciling.

## Bounds and retained state

The new live-model gateway has a fixed 24-request/80,000-token allowance, 2,048 output tokens per request, and a 64 KiB request ceiling. Jev stops after dispatch and admits at most 12 classification requests. Neither allowance automatically resets. The old chat allowance is separate.

The native agents use Substrate snapshots and native controller TaskStore records. The bridge admission and workflow states, and the tool service's proposal/review/decision/merge receipts, persist on separate PVCs. Automatic native context compaction remains unverified. Browser updates show saved native artifacts rather than token-by-token streaming.

GitLab's numeric IDs are normalized from Protobuf Struct floats only after matching the canonical recorded binding. A changed head, target manifest, missing CI or review, expired decision, or uncertain prior merge attempt prevents merging. An ambiguous merge response is read back from GitLab; it is not automatically retried.

The agent's project access token expires **21 October 2026**. Flux's repository-read deploy token expires **14 November 2026**. Renew credentials before rehearsals after those dates. Secret values, rendered Secret manifests and raw proof files are ignored local state, not this document.

## Verification scope

The human approved the real native gate at 12:07 UTC on 14 October. GitLab merged MR !1 at 12:07:50 UTC with commit `bbbb59d121eb4cf96cabd95ba4aa716a582fb09a`. Flux applied `main@sha1:bbbb59d121eb4cf96cabd95ba4aa716a582fb09a`; the live Deployment is on v1, generation 3 observed and available. Three probes returned HTTP 200, version v1 and total 20. The separate native post-Flux verification task `01a13a50-73de-7f21-9f82-0b4137096153` completed with the matching actual verification receipt. `capture-gitops.py --expect completed` independently passed native, GitLab and Kubernetes checks. Raw proof is `.data/gitops-completed-proof.json`. The model gateway recorded 10/24 requests and 41,285 reported tokens, with its original allowance preserved.

Healthy v1 was measured with three HTTP 200 requests before introducing the fault. Flux then applied the real v2 fault commit. Native investigation, real MR creation, exact-head CI and native review were verified before exposing the human gate. The recorded decision and independent post-merge proof above establish application recovery.

The first native investigation hit the gateway's former 16 KiB request ceiling after collecting evidence. It is retained as a failed task. The same native context continued after compacting tool payloads and raising only the request-size ceiling; its budget ledger was preserved. A clean rehearsal run is separate from this retained setup run.

## Source

`gitops/application.py` and `Dockerfile.app` build both application versions. `gitops/mcp.py` implements the real tools, classification monitor and independent ledger. `gitops.py` observes native tasks, orchestrates review and post-rollout verification, and translates the workflow to the pane. `deploy-chat.py --mode gitops` provisions the bounded native pair. Initial environment installation and controlled fault injection are operator setup scripts; repeat/reseed is not yet a UI control.

Flux resources follow its [GitRepository](https://fluxcd.io/flux/components/source/gitrepositories/) and [Kustomization](https://fluxcd.io/flux/components/kustomize/kustomizations/) contracts. Merge uses the [GitLab merge requests API](https://docs.gitlab.com/api/merge_requests/) SHA precondition.
