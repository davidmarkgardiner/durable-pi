<script setup lang="ts">
import { ArrowRight, Check, Send } from "lucide-vue-next";
import type { IncidentHandoff } from "@sdk/jobs";
defineProps<{ handoff: IncidentHandoff; compact?: boolean }>();
const percentage = (value: number) => `${Math.round(value * 100)}%`;
const time = (value: number) => new Date(value).toLocaleTimeString('en-GB', { timeZone: 'UTC', hour12: false }) + ' UTC';
</script>

<template>
  <section class="incident-handoff" :class="{ compact }" aria-label="Classifier to agent handoff">
    <header><Send :size="18" /><h3>How the incident reached the agent</h3><span v-if="handoff.delivery.kind === 'accepted'" class="delivered"><Check :size="14" />Delivered</span></header>
    <ol class="handoff-chain">
      <li><strong>Application responses</strong><span>{{ handoff.samples.length }} × HTTP 500</span><small>Guest checkout on v2</small></li>
      <li class="flow-arrow" aria-hidden="true"><ArrowRight :size="18" /></li>
      <li><strong>{{ handoff.source }}</strong><span>{{ handoff.samples.map(sample => sample.decision).join(' · ') }}</span><small>{{ handoff.samples.map(sample => percentage(sample.probability)).join(' · ') }} incident probability</small></li>
      <li class="flow-arrow" aria-hidden="true"><ArrowRight :size="18" /></li>
      <li><strong>Pi dispatch policy</strong><span>{{ handoff.policy.matched ? 'Threshold met' : 'Threshold not confirmed' }}</span><small>{{ handoff.policy.minimumIncidents }} incidents ≥ {{ percentage(handoff.policy.minimumProbability) }}</small></li>
      <li class="flow-arrow" aria-hidden="true"><ArrowRight :size="18" /></li>
      <li><strong>Native specialist</strong><span>{{ handoff.delivery.kind === 'accepted' ? 'Message accepted' : 'Admission unconfirmed' }}</span><small>{{ handoff.transport }}</small></li>
    </ol>
    <p v-if="!compact" class="handoff-explanation">{{ handoff.source }} classifies the responses. The Pi bridge applies the threshold and sends the investigation message to kagent. The agent then fetches detailed application logs through MCP.</p>
    <details>
      <summary>View exact instruction and delivery receipt</summary>
      <div class="sent-message"><strong>Exact instruction sent to the agent</strong><p>{{ handoff.instruction }}</p></div>
      <dl>
        <dt>Dispatcher</dt><dd>{{ handoff.dispatcher }} · {{ handoff.transport }}</dd>
        <dt>Recipient</dt><dd>{{ handoff.agent }}</dd>
        <dt>Trigger time</dt><dd>{{ time(handoff.triggeredAt) }}</dd>
        <dt>Request ID</dt><dd>{{ handoff.requestId }}</dd>
        <dt>Message ID</dt><dd>{{ handoff.messageId }}</dd>
        <dt>Native context</dt><dd>{{ handoff.contextId }}</dd>
        <template v-if="handoff.delivery.kind === 'accepted'">
          <dt>Native task</dt><dd>{{ handoff.delivery.taskId }}</dd>
          <dt>Original task state</dt><dd>{{ handoff.delivery.taskState }}</dd>
        </template>
      </dl>
      <p v-if="handoff.delivery.kind === 'accepted'">Delivery is confirmed by the native task history matching this message ID, context and exact instruction.</p>
      <p v-else class="message-error">{{ handoff.delivery.reason }}</p>
      <p>The initial instruction contains the incident summary. The agent calls <code>read_incident</code> to fetch the current checkout response and pod logs. The Logs tab retains the original responses and classification decisions.</p>
      <table><thead><tr><th>Response time</th><th>Decision</th><th>Probability</th></tr></thead><tbody>
        <tr v-for="sample in handoff.samples" :key="sample.at"><td>{{ time(sample.at) }}</td><td>{{ sample.decision }}</td><td>{{ percentage(sample.probability) }}</td></tr>
      </tbody></table>
    </details>
  </section>
</template>

<style scoped>
.incident-handoff { border: 1px solid #65532e; border-radius: 10px; padding: 16px; background: #7b64160c; margin-bottom: 20px; }
header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
h3 { font-size: 14px; }
.delivered { display: flex; align-items: center; gap: 4px; color: #a5dab4; font-size: 11px; margin-left: auto; }
.handoff-chain { display: flex; gap: 7px; list-style: none; margin: 0; padding: 0; }
.handoff-chain li:not(.flow-arrow) { flex: 1; min-width: 0; display: grid; align-content: start; gap: 7px; border: 1px solid var(--line); border-radius: 7px; padding: 10px; }
.handoff-chain strong { font-size: 11px; color: var(--muted); }
.handoff-chain span { font-size: 12px; overflow-wrap: anywhere; }
.handoff-chain small { font-size: 10px; line-height: 1.6; color: var(--muted); }
.flow-arrow { display: flex; align-items: center; color: var(--muted); }
p { font-size: 12px; line-height: 1.6; margin: 12px 0; }
summary { cursor: pointer; color: var(--accent); font-size: 12px; margin-top: 12px; }
.sent-message { padding: 12px; background: var(--surface); border-radius: 7px; margin-top: 14px; }
.sent-message strong { font-size: 12px; }
dl { display: grid; grid-template-columns: 110px minmax(0,1fr); gap: 8px 12px; font-size: 11px; margin: 16px 0; }
dt { color: var(--muted); } dd { margin: 0; overflow-wrap: anywhere; font-family: 'IBM Plex Mono', monospace; }
table { width: 100%; font-size: 11px; border-collapse: collapse; } th,td { text-align: left; padding: 7px; border-bottom: 1px solid var(--line); }
.compact { padding: 12px; } .compact header { flex-wrap: wrap; } .compact .handoff-chain { display: grid; grid-template-columns: 1fr 1fr; } .compact .flow-arrow { display: none; }
@media (max-width: 700px) { .handoff-chain { display: grid; grid-template-columns: 1fr 1fr; } .flow-arrow { display: none; } }
</style>
