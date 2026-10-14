# Work-agent assignment

Reproduce the Pi proactive application remediation demo on the approved remote Kubernetes demo cluster using this bundle.

Use the bundled Pi pane and native kagent agents. Replace Jev with the included, explicitly labelled scripted synthetic decision rule. Keep the application requests, native A2A handoff, MCP investigation, GitLab MR, CI, human merge approval, Flux rollout and final verification real.

Read README.md, CHECKPOINTS.md and CONNECTIONS.md first. Inspect the target cluster and current kagent API before making changes. Fill profile.json from profile.example.json using verified workplace values. Ask for missing target names or approved credentials early while continuing source/build checks. Do not use any home-lab context, project, endpoint or credential.

The implementation targets native kagent 1.x AgentTemplate/Harness resources and the native gRPC controller API. If the cluster uses 0.x or a different protocol, report the exact incompatibility and prepare an adapter proposal. Do not upgrade or replace kagent, Istio, AKS add-ons, models, or existing agents.

Reuse an existing approved ModelConfig and inspect the seed Harness before cloning it. Verify the existing model route has an enforced allowance for this demo. The scripted classifier needs no API key and makes no model calls. Run source tests and build the runtime/UI. Use a dedicated empty GitLab project, fresh application namespace, fresh run ID, approved image registry and referenced workplace Secrets. Review the exact generated manifests and repository files before creating them.

Use loopback port-forwarding first. The UI runs on the workstation; the Pi bridge, agents and app run on the remote cluster. Optionally route only the bridge HTTP endpoint through the existing Istio Gateway when that route is approved. Do not expose MCP services or the native controller to the browser.

Deliver a working Pi UI at its complete literal URL. Run scripts/refresh-inventory.py to collect current native declarations and controller MCP discovery. Show the native agents, configured model, actual tool bindings, synthetic classification events and exact A2A delivery receipt. Click Start synthetic incident once. Let the specialist investigate the real v2 failure, create the image-only rollback MR, and hand the exact head to the read-only reviewer.

Stop at the native approval card and let David make the merge decision. Do not submit approval yourself or treat this assignment as merge approval. Before the human click, capture the awaiting_approval receipt, exact MR URL and head SHA, successful checkout-tests pipeline, reviewer task, native INPUT_REQUIRED task and approval ID.

After the human approves, observe the real merge. Verify the merge SHA equals both Flux source and applied revisions, the deployment uses the healthy image, and three actual guest checkout requests return HTTP 200 with total 20. Obtain the specialist's final verify_application MCP receipt. Capture the completed proof and a screenshot of the Pi result.

Return checkpoint results as verified, blocked, or pending. Do not call generated plans or synthetic decisions autonomous reasoning. Do not call a deployment receipt end-to-end proof. Preserve workflow PVCs, native contexts and uncertain-write evidence. This bundle is a single-run demo; prepare a fresh scoped run instead of resetting approval or admission ledgers.
