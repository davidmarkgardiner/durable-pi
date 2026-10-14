# Pi home-lab demo for the kagent comparison

Verified on 14 October 2026. This is the Durable Pi side of the comparison. The Pi backend, queue worker, agents, SQLite state and worktrees run in the `pi-durable-lab` Proxmox VM. The Mac runs the web hub and an SSH tunnel; closing the Mac browser does not stop VM work.

## Open the live pane

Open http://127.0.0.1:4781/ on this Mac. In the left tree select **proxmox → Queue · microsoft-pi-20261014 → Investigator / Builder**. Select **Read-only Reviewer** to see its independent verdict. The **Tasks**, **Tools** and **State** tabs show the approval, offered tools and shared incident record.

The new queue job `microsoft-pi-20261014` finished `PASS` in `/home/david/dpi-work/queue-worktrees/microsoft-pi-20261014` on branch `queue/microsoft-pi-20261014`. The builder recorded a failing baseline, implemented explicit empty-cart rejection, and saved before/after test output. Seven final tests passed. The reviewer read the evidence with `readOnly: true`; it had no shell or file-write tools and did not rerun the tests. The coordinator saved the verdict and read it back from `/incidents/job-microsoft-pi-20261014`.

**Release check task #141 is waiting for a human decision.** Its plan and subagent gather phases completed. Publish and verify remain pending. Its approval survived a live `dpi-backend` service restart on 14 October with the same task ID and pending decision. Selecting **Approve & continue** writes synthetic release notes to Pi App State at `/jobs/release-check`; it does not merge, deploy or publish externally. Selecting **Decline** records a refusal. Leave the card pending if demonstrating the checkpoint.

## Walkthrough

1. Show **2 of 2 devices online** and the `proxmox` device in the left tree. This is the front pane across the Mac and VM, connected over the SSH tunnel.
2. Expand the new queue session and open **Investigator / Builder**. Expand tool calls to show `PLAN.md`, baseline tests, code edits, seven passing final tests and the handoff.
3. Open **Read-only Reviewer**. Its verdict is `PASS`, with explicit limitations. The reviewer did not run tests or approve a deployment.
4. Return to **Investigator / Builder**. Show task #141's plan, gather subagent, and the **Approve** phase waiting. The **Publish** and **Verify** phases have not run.
5. If the demonstration includes a decision, use the card's **Approve & continue** or **Decline** control. After approval, check the same card for completed Publish and Verify phases and inspect `/jobs/release-check` in **State**. A decision is not necessary to show durability.

## Health and recovery commands

From this checkout on the Mac:

```sh
PATH="$HOME/.dpi/remote-pi/bin:$HOME/.nvm/versions/node/v24.15.0/bin:$PATH" just net status
PATH="$HOME/.dpi/remote-pi/bin:$HOME/.nvm/versions/node/v24.15.0/bin:$PATH" just net probe proxmox
$HOME/.dpi/remote-pi/pi-queue status
ssh -F "$HOME/.dpi/remote-pi/ssh_config" pi-durable-proxmox 'systemctl is-active dpi-backend dpi-task-queue'
```

The Mac tunnel is `dev.dpi.proxmox-tunnel`, forwarding `127.0.0.1:4784` to the VM's `127.0.0.1:4780`. On 14 October, DHCP moved the VM from `192.168.4.97` to `192.168.4.101`; the matching SSH host key was checked and the private SSH config updated. If the device goes offline again, discover VM 111's current IP with `ssh proxmox 'qm guest cmd 111 network-get-interfaces'`, verify its SSH host key, update `$HOME/.dpi/remote-pi/ssh_config`, then run `launchctl kickstart -k gui/$(id -u)/dev.dpi.proxmox-tunnel`. Do not assume today's IP is stable.

## Scope

The VM queue accepts explicit jobs and runs them serially. Each new job gets a branch, worktree, Pi session and investigator/reviewer pair. This is a synthetic software task; it does not poll a software-factory backlog or distribute jobs across multiple worker machines. Pi checkpoint recovery and the home-lab front pane have been exercised. Native kagent actors and its UI are the other side of the comparison; this Pi backend is not a kagent actor or adapter.
