# Reusing the pane with kagent at work

The home-lab POC answers the main connection question. The existing Pi hub can show native kagent agents, saved tool calls/results and the native human approval while execution remains in Kubernetes. It needs a protocol adapter because Pi's device/session/conversation/SSE contract differs from kagent's Agent/Session/A2A/HITL contract.

The original synthetic checkout application runs in Kubernetes and generates actual exceptions. Real TypeSafe Jev decisions open the incident automatically after three matching incident rows at probability at least 0.6 inside 120 seconds. Jev is a separate service before the agent. At work, an approved decision model must implement the same classification contract, with representative normal/warning/error acceptance cases. The generation model used by the coding agent is a separate choice.

The current POC uses scripted native reasoning and a separate protected synthetic effect fixture. The original checkout source is not repaired or rolled out by the native actor. Its UI disables unsupported creation and chat controls and states that scope. Native actors, MCP tool calls, TaskStore persistence, review and the pending native approval are real.

## Work remaining for the original autonomous demo

| Work | Result | Rough effort with a compatible installed kagent/Substrate lab |
| --- | --- | --- |
| Native MCP tools for the original checkout app | Log queries, isolated Git worktrees, source edits, baseline/fix test gates, bounded rollout and traffic verification | 1–2 engineering days |
| Approved live reasoning model | Autonomous investigation/fix, request and token limits, failure reconciliation | 0.5–1 day |
| Complete UI mapping and proof | Native input/follow-up, permission-aware controls, streaming, approval/denial continuation and matched recovery checks | 1–2 days |

Allow roughly 3–5 focused engineering days for a faithful demo, after model access and compatible cluster APIs are confirmed. This is an estimate based on the existing tools and inspected interfaces. Workplace identity, RBAC, gateway routing, secret injection and network rules require validation in the actual environment and can add time. A home-lab result does not establish those workplace prerequisites.

For the first workplace rehearsal, deploy the synthetic application, classifier and bounded tool service into a dedicated namespace. Keep the existing kagent UI available alongside the shared hub as an independent view. Require a real human decision at native `requireApproval` before the synthetic rollout. Record its exact task/context/proposal, then independently verify traffic and effects. Once that passes, a software-factory adapter can submit explicit backlog work without changing the presentation layer.
