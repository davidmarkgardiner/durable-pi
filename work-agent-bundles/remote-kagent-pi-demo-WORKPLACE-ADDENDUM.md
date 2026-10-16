# Run the workplace demo with kagent only

16 October 2026. This page supersedes the Pi and Substrate requirements in [START-HERE.md](remote-kagent-pi-demo/START-HERE.md) for the workplace attempt. Use the existing regular kagent agents and workplace interface. Do not deploy Pi, Durable Pi, the Pi UI, or the Pi bridge. David reports that Substrate is disabled pending Azure policy approval. The workplace configuration has not been inspected here.

## Prepare the demo images

Build or import the following through the bank's approved process. Reuse existing copies only when source revision, build arguments, and digests match. Run builds from `remote-kagent-pi-demo/` with `runtime/` as the build context.

| Profile field | Build recipe | Workplace purpose |
| --- | --- | --- |
| `runtime_image` | `runtime/Dockerfile` | Demo MCP tools backend for Kubernetes inspection, GitLab rollback, and verification. Override the default command with `python /app/tools.py`. Do not start `work_bridge.py`. |
| `healthy_image` | `runtime/Dockerfile.app`, `APP_VERSION=v1` | Healthy checkout application and rollback target. |
| `regression_image` | `runtime/Dockerfile.app`, `APP_VERSION=v2` | Deliberately broken checkout application for the synthetic incident. |

Three custom images remain if the bundled MCP backend is retained. If existing approved workplace tools provide the same scoped operations and approval controls, adapt to those tools and omit the custom backend image. The two checkout images remain. Reuse the installed approved kagent runtime and ModelConfig separately.

Both Dockerfiles default to `python:3.12.12-slim-bookworm` and accept `PYTHON_BASE` for an approved mirror. Make `runtime/requirements.lock` dependencies available to the builder. The generated GitLab CI also names that Python image. Update its reference when an internal mirror is required.

David needs to identify the approved registry paths and build/import route if unavailable to the work agent. Discover the target architecture and image-pull Secret references. Record the source commit and image digests in the private profile. Verify image availability on target nodes.

## Use the dev pod without requiring Podman

Podman is optional. Use existing CI or an approved remote builder. The dev pod can run source checks, generate plans, and use approved Kubernetes access. It does not automatically provide an image builder. Do not add privileged nested containers or mount a host engine socket.

Prefer registry pulls. For an approved kind-only loading route, its host operator can use `kind load image-archive IMAGES.tar --name VERIFIED_CLUSTER_NAME`. Load every eligible node and use a compatible pull policy such as `IfNotPresent`. Images stored only inside the dev pod are insufficient. [kind image loading](https://kind.sigs.k8s.io/docs/user/quick-start/#loading-an-image-into-your-cluster)

## Adapt to the working kagent configuration

Keep Substrate disabled. Inspect the target context, kagent version, served APIs, a Ready regular agent and its Deployment, ModelConfig reference, MCP bindings, and A2A/session/approval protocol. Read Secret references without exporting values. Derive the specialist and read-only reviewer from working declarations. Preserve existing agents and platform settings.

The original preflight and renderer require 1.x `AgentTemplate`/`Harness` resources. Upstream 1.x sessions require Substrate; Deployment-based regular agents exist in 0.x. Use the observed workplace API and adapt these scripts rather than copying the original Harness. [kagent 1.x runtime](https://kagent.dev/docs/kagent/1.x/about/core-concepts/), [regular agents](https://kagent.dev/docs/kagent/0.x/concepts/agents/)

Replace the Pi start button, incident dispatch, inventory, approval delivery, and verification with the existing kagent interface and supported APIs. Starting `tools.py` alone does not perform these functions. If retaining the bundled tools, connect the real human decision to its independent ledger, which currently requires native task and approval IDs. Never fabricate IDs or bypass that gate. Validate this integration before launch.

Keep the real MCP investigation, exact-head MR/CI review, David's merge decision, Flux reconciliation, and final checkout probes. Label classification synthetic. Report unsupported approval or task semantics as a blocker. Return image digests, sanitized discovery, adaptation checks, and remaining blockers. This is a documentation correction, not a completed adapter. Retain the original bundle checksums and ZIP unchanged.
