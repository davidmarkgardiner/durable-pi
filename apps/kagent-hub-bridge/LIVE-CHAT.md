# Live native chat in the Pi pane

Open http://127.0.0.1:4781/ and choose **kagent-proxmox → Live Kimi chat → Live Kimi specialist**. The same composer now sends ordinary messages to a native kagent session running on the installed Kubernetes/Substrate runtime. **Live Kimi reviewer** has its own session and the same message box.

Type `/` for the supported commands: `/tasks`, `/tools`, `/skills`, `/models`, `/logs` and `/help`. These commands run in the UI and spend no model requests. The current adapter admits one active task per agent. Steering, queue withdrawal, reset, compaction, forks, model changes and interruption are not exposed as native chat controls.

The specialist and reviewer use live Kimi through a fresh bounded gateway. They have only the existing `read_incident`, `get_operation` and `read_result` MCP tools. They can investigate the synthetic fixture, discuss evidence and propose actions in text. They cannot write source, mutate the cluster, create/merge PRs or approve the retained incident's gate. The incident tool reports fixed synthetic baseline evidence; operation/result tools expose current proposal and effect state.

The gateway has a persistent allowance of eight model requests and 20,000 charged/reserved tokens across both agents. Its ledger and the pane's reported-token counter persist across bridge restarts. This is a bounded home-lab chat demo. Provider completions are buffered by the gateway; the pane observes native task and tool updates through SSE snapshots rather than token-by-token provider streaming.

## Admission and recovery

The bridge persists each user request before native SendMessage. It binds the stable browser request ID to one role, message body and native message ID. Repeating that request returns the existing submission. Reusing its ID with different text returns HTTP 409. A new request during unresolved work also returns HTTP 409.

An uncertain admission is reconciled against native ListTasks and its message ID. It is never automatically resent. An explicit controller refusal allows an exact client retry. Each admitted task is read back from native TaskStore; its original context ID remains stable across subsequent tasks. UI artifacts come from those saved native task artifacts.

The proactive synthetic incident retains its original native task and proposal. A human approval was recorded at 10:22 UTC on 14 October, then stalled because protobuf returned numeric revision `1.0` while the protected fixture requires a strict integer. The adapter normalizes integral revisions at that boundary and resumed the saved decision without changing its task, hash or expiry. Independent readback confirms one synthetic effect and a successful native result. Chat messages do not issue those decisions.

## Verification receipts

Eighteen Python interpretation/admission tests pass, including duplicate-send, busy-agent rejection, uncertain admission after restart, retained context, budget exhaustion, stale approval binding and strict revision conversion. Frontend type/build checks and lint pass.

The live browser test sent an investigation request, observed a native `read_incident` tool call and Kimi diagnosis, then sent a follow-up in the same native session. Kimi remembered `PI-CHAT-514` and named `read_incident` as the evidence source. A reviewer chat turn verifies the second role. `capture-chat.py` reads actual native tasks and gateway usage, replays the original request without another model call, and rejects content-changing request reuse, steering and ordinary approval text sent to the retained incident.

Private receipts are `.data/chat-proof.json` and `.data/live-proof.json`. They contain native session/task identities and artifacts without provider keys. `deploy-chat.py` creates fresh named resources and refuses to replace an existing retained chat. Runtime configuration and client tokens remain in Kubernetes Secrets and private deployment state.
