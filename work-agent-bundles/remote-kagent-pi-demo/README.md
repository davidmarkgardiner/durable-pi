# Remote kagent demo from the Pi pane

Hand START-HERE.md and this entire directory to the work agent. This is runnable source, not a captured replay. The workplace cluster has not been contacted by the author of this bundle.

## What the audience sees

1. Two durable native agents in the Pi tree, with tools and configured model visible.
2. A Start synthetic incident button. It changes the dedicated GitLab deployment manifest from the healthy image to the faulty image. Flux deploys it.
3. Three actual guest checkout HTTP 500 responses. A clearly labelled scripted HTTP-status rule classifies them as incidents. It uses no Jev, external classifier or API key.
4. The Pi bridge sends an A2A investigation message to the native specialist. The handoff panel displays the exact instruction, message ID, context and native task receipt.
5. The specialist uses the scoped Kubernetes/repository MCP tools and creates a real GitLab MR that changes only the deployment image back to v1.
6. A read-only native reviewer checks the exact diff and successful CI head. The specialist pauses on kagent's native merge_mr approval. Pi displays the MR link, head SHA, proposed effect and Approve/Decline buttons.
7. The human approves in Pi. The native task resumes; the independent decision ledger also checks this exact MR/head before GitLab merge.
8. Flux applies the merge. The specialist's final tool receipt confirms the healthy image and three HTTP 200 checkout requests.

The specialist is guided with application knowledge and the known healthy image. The decision rule is scripted. Investigation/tool execution and the MR workflow are real. This demonstrates image rollback through GitOps, not an autonomous source-code repair agent.

## Requirements and boundaries

- Native kagent 1.x, Agent/AgentTemplate/Harness v1alpha3 and the kagent.api.v1alpha1 / lf.a2a.v1 controller APIs. Verified against 1.0.0-alpha11. Other versions require the connection checks; 0.x requires a separate adapter.
- An existing approved ModelConfig, ready seed agent/Harness, durable native session storage and an enforced model allowance. The bundle does not install or choose a model. Its prompt limits are not a provider quota.
- Existing Flux source and kustomize controllers. If the workplace deployer differs, stop and identify the required reconciliation adapter. The bundle does not install Flux.
- A dedicated empty GitLab project with a usable CI runner. API credentials must permit branch/commit/MR/merge only in that project. Protected-main policies must allow the explicit demonstration fault commit. GitLab repository approval requirements still apply.
- Existing API Secret in agent_namespace, containing gitlab_secret_key. Only the MCP backend mounts it. Existing Flux repository-read Secret in flux_namespace, with the credentials Flux expects. No credentials are included.
- Three images built from runtime: runtime, checkout v1, checkout v2. Push to the approved registry using established authentication. Verify cluster image pulls, and mirror base/CI images if needed. No air-gap claim is made.
- Approved persistent RWO storage. The app namespace must be fresh. If flux_namespace differs, it must already exist. Existing agent namespace is reused.
- Python 3.12+, kubectl, Docker/build tooling and Node 24+ with npm on the appropriate build/workstation hosts.

Skills start empty. The app knowledge is the specialist's system prompt. Bind only reviewed workplace skills and verify native discovery before describing them as loaded. The Models tab lists configured ModelConfigs after refresh-inventory.py runs. The bundle reuses the selected route and installs no models.

## Preparation

```sh
python3 scripts/check-package.py
cp profile.example.json profile.json
# Fill exact approved values. Keep local profiles and generated state private.
PYTHONPATH=runtime python3 -m unittest discover -s tests -v
python3 scripts/preflight.py --profile profile.json
```

Review the seed Harness's runtime references, snapshot settings, network access and environment references. The renderer copies its spec, reuses the approved ModelConfig, and replaces the system prompt and tool bindings. It removes inherited skills to avoid claiming unrelated app knowledge.

Build on a suitable approved Linux/container builder. Choose image architecture for the cluster. Substitute profile image names explicitly; these examples intentionally contain placeholders.

```sh
docker build -f runtime/Dockerfile -t APPROVED_RUNTIME_IMAGE runtime
docker build -f runtime/Dockerfile.app --build-arg APP_VERSION=v1 -t APPROVED_HEALTHY_IMAGE runtime
docker build -f runtime/Dockerfile.app --build-arg APP_VERSION=v2 -t APPROVED_REGRESSION_IMAGE runtime
```

Push/import those exact images through the approved registry process. Pin digests in the profile when available. A base-image override is supported with --build-arg PYTHON_BASE=APPROVED_BASE_IMAGE.

## Seed and install

```sh
python3 scripts/seed-repository.py --profile profile.json --output .state/repository-plan
```

This generates files, runs checkout tests and checks the Kustomize render. It makes no GitLab write. Review the plan. To seed an empty dedicated project, use a new output directory and a private token file through the approved workplace credential mechanism:

```sh
python3 scripts/seed-repository.py --profile profile.json --output .state/repository-seed --token-file PRIVATE_TOKEN_FILE --commit
python3 scripts/render.py --profile profile.json --state .state/install
python3 scripts/install.py --profile profile.json --state .state/install
```

The rendered resources contain newly generated bridge/control/role capability tokens. They are private, not a shareable manifest. The default install command checks name collisions and native schemas without creating resources. Review resources.json privately, then create the scoped installation:

```sh
python3 scripts/install.py --profile profile.json --state .state/install --create
```

Create stops on any existing resource rather than overwriting it. A partially created installation requires inspection and a plan to continue; do not delete state or rerun with a new identity blindly. Cluster permissions, namespace policy, image pulls, mesh policy and Secret references may still block actual readiness despite schema validation.

## Connect and run

See CONNECTIONS.md. In separate terminals on the workstation:

```sh
python3 scripts/connect.py port-forward --profile profile.json --state .state/install
cd ui/apps/dpi-sdk && npm ci
cd ../dpi-playground && npm ci && npm run build
```

Return to the bundle root:

```sh
python3 scripts/connect.py ui --profile profile.json --state .state/install
```

Open http://127.0.0.1:4781/. The hub uses an isolated registry in .state/install. It holds the bridge token server-side; the browser does not receive Kubernetes credentials or the GitLab PAT. Verify pods, agents and Flux are Ready and the healthy app is deployed. Collect current native model/skill declarations and controller MCP discovery into the pane:

```sh
python3 scripts/refresh-inventory.py --profile profile.json --watch
```

Keep that read-only metadata collector running during the presentation. It refreshes the bridge's inventory file every 45 seconds and reads no Secret values. The UI refresh button rereads this inventory. Actual use still requires native task receipts. Before clicking Start synthetic incident, confirm the specialist's merge_mr binding requires approval and the reviewer offers no write tools. That button makes the real scoped fault commit. Only David clicks the merge approval.

```sh
python3 scripts/verify.py --profile profile.json --state .state/install --expect connected --output .state/connected.json
python3 scripts/verify.py --profile profile.json --state .state/install --expect awaiting_approval --output .state/awaiting-approval.json
# After the human's approval and recovery:
python3 scripts/verify.py --profile profile.json --state .state/install --expect completed --output .state/completed.json
```

Verification reads current native controller tasks and GitLab/Kubernetes receipts through the bridge. It never submits approval. Capture rendered UI screenshots as well. CHECKPOINTS.md defines the required live evidence.

## Durability and limits

Two native session IDs, request/message IDs, workflow transitions and uncertain admissions persist in the bridge PVC. The independent tool/approval ledger persists in the tools PVC. Native sessions remain under the existing controller/TaskStore/Harness policies. Persisted state rejects a different agent identity. Existing snapshot and automatic compaction behavior is not proved by this package; verify it on the target before describing it in a presentation.

The single run has a ten-minute regression-observation deadline and at most twelve scripted v2 decisions. It waits for v2 without consuming decisions on healthy v1 responses. It does not reset model quotas, repeat uncertain writes or automatically retry a failed native model task. A stale approval expires after fifteen minutes. A failed task or expired decision is a blocker requiring explicit reconciliation.

To stop the presentation, stop UI and port-forward processes. Do not remove PVCs, native contexts, branches or namespaces as part of stopping. Cleanup or a repeat demonstration needs a reviewed fresh scope and retained receipts.
