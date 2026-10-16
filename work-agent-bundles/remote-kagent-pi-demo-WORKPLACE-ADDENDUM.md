# Proceed with approved images and regular kagent agents

16 October 2026. Give this page to the work agent alongside [START-HERE.md](remote-kagent-pi-demo/START-HERE.md). This page supersedes its Substrate-dependent runtime requirement for the current workplace attempt. David reports that Substrate is disabled pending Azure policy approval. The workplace configuration has not been inspected here.

## Prepare the three demo images

Yes, build or import these custom images through the bank's approved process before deploying the demo. Reuse existing copies only when their source revision, build arguments, and digests match. Run builds from `remote-kagent-pi-demo/` with `runtime/` as the build context.

| Profile field | Build recipe | Purpose |
| --- | --- | --- |
| `runtime_image` | `runtime/Dockerfile` | One shared image for the Pi bridge and MCP tools backend, with different startup commands. |
| `healthy_image` | `runtime/Dockerfile.app`, `APP_VERSION=v1` | Healthy checkout application and rollback target. |
| `regression_image` | `runtime/Dockerfile.app`, `APP_VERSION=v2` | Deliberately broken checkout application for the synthetic incident. |

These are demo application images. Reuse the installed approved agent runtime and ModelConfig separately. Both Dockerfiles default to `python:3.12.12-slim-bookworm` and accept `PYTHON_BASE` for an approved mirror. Make `runtime/requirements.lock` dependencies available to the builder. The generated GitLab CI also names that Python image. Update its reference when an internal mirror is required.

David needs to identify the approved registry paths and build/import route if these are unavailable to the work agent. The work agent can discover the target architecture and existing image-pull Secret references, then prepare builds. Record the source commit and resulting digests, then fill `runtime_image`, `healthy_image`, and `regression_image` in the private profile. Verify actual image availability on the target nodes before launch.

## Use the existing dev pod without requiring Podman

Podman is optional. Use the bank's existing CI or approved remote builder. The dev pod can run source checks, generate plans, and use its approved Kubernetes access. A running dev pod does not automatically provide an image builder or access to the host's image store. Do not add privileged nested containers or mount a host engine socket for this demo.

Prefer registry pulls. If this is genuinely a kind cluster and local image loading is approved, its host operator can use `kind load image-archive IMAGES.tar --name VERIFIED_CLUSTER_NAME`. Load every eligible node and use a compatible pull policy such as `IfNotPresent`. An image stored only inside the dev pod is insufficient. [kind image loading](https://kind.sigs.k8s.io/docs/user/quick-start/#loading-an-image-into-your-cluster)

## Adapt to the working regular-agent configuration

Keep Substrate disabled. Inspect the approved target context, installed kagent version, served API groups, one Ready regular agent, its Deployment, ModelConfig reference, MCP bindings, and actual A2A/session/approval protocol. Read Secret references without exporting Secret values. Derive the new specialist and reviewer from those working declarations. Preserve existing agents and platform settings.

The original bundle requires 1.x `AgentTemplate`/`Harness` resources and native gRPC APIs. Its `scripts/preflight.py` enforces that schema, and `scripts/render.py` copies the seed Harness. Upstream 1.x sessions require Substrate. Deployment-based regular agents exist in 0.x. Changing an image or removing a Harness field cannot provide compatibility. [kagent 1.x runtime](https://kagent.dev/docs/kagent/1.x/about/core-concepts/), [regular agents](https://kagent.dev/docs/kagent/0.x/concepts/agents/)

Prepare and validate an adapter for the observed API, including manifests, bridge session/task handling, inventory, verification, and human approval. Keep the real MCP investigation, exact-head MR/CI review, David's merge decision, Flux reconciliation, and final checkout probes. Keep classification labelled synthetic. If approval or task semantics cannot be preserved, report that specific blocker before launch. Do not claim snapshot recovery or end-to-end success from generated manifests or source tests.

Return the image digests, sanitized discovery, adapter changes and checks, and remaining blockers. Continue source/build preparation while image access is arranged. Retain the original bundle's checksums and ZIP unchanged; this page is a separate addendum.
