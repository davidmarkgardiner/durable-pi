<script setup lang="ts">
import { computed } from "vue";
import { deviceFeed, selected } from "../client/store";
import { jobRuns } from "../client/jobs";
import IncidentHandoff from "./IncidentHandoff.vue";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function record(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}
const proactive = computed(() => record(record(deviceFeed.sharedState.value?.value).proactive));
const gitops = computed(() => record(record(deviceFeed.sharedState.value?.value).gitops));
const gitopsSelected = computed(() => jobRuns.value.some(run => run.job === "native-kagent-gitlab-merge") || selected.value?.sessionId === gitops.value.workspaceId || selected.value?.sessionId.startsWith("native-gitops-"));
const synthetic = computed(() => record(gitops.value.classifier).mode === "synthetic");
const decisionSource = computed(() => synthetic.value ? "Synthetic decision · scripted HTTP rule" : "TypeSafe · jev-latest");
const classifications = computed(() => Array.isArray(gitops.value.classifications) ? gitops.value.classifications.map(record) : []);
const handoff = computed(() => jobRuns.value.find(run => run.job === 'native-kagent-gitlab-merge')?.incidentHandoff);
const classifier = computed(() => record(proactive.value.classifier));
const rows = computed(() => {
  const value = proactive.value.logs;
  if (!Array.isArray(value)) return [];
  return value.map((item: unknown) => record(item)).filter((item) => typeof item.id === "number")
    .sort((a, b) => Number(Boolean(b.decision)) - Number(Boolean(a.decision)) || Number(b.id) - Number(a.id));
});
const connection = computed(() => record(proactive.value.connection));
const nativeError = computed(() => record(proactive.value.error));
const trigger = computed(() => record(proactive.value.trigger));
const text = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : "";
</script>

<template>
  <section class="proactive-logs" aria-label="Proactive log classifications">
    <template v-if="gitopsSelected">
      <div class="panel-heading"><h2>Checkout incident evidence</h2></div>
      <p class="hint">Actual requests to the synthetic checkout service. {{ synthetic ? 'A scripted HTTP-status rule' : 'TypeSafe Jev' }} classifies the HTTP failures. The Pi bridge triggers the native specialist after three incident judgments.</p>
      <div class="classifier-status"><strong>{{ decisionSource }}</strong><span>{{ text(gitops.calls) }} / 12 {{ synthetic ? 'decisions' : 'requests' }}</span><span>Workflow: {{ text(record(gitops.workflow).phase) }}</span></div>
      <IncidentHandoff v-if="handoff" :handoff="handoff" compact />
      <div v-else-if="gitops.trigger" class="trigger-proof"><strong>Dispatch threshold reached</strong><span>Three checkout responses were classified as incidents. The Pi bridge sends an A2A message to the native specialist.</span></div>
      <p v-if="gitops.monitor_error || gitops.connectionError" class="message-error">{{ text(gitops.monitor_error || gitops.connectionError) }}</p>
      <article v-for="(item, i) in classifications" :key="i" class="log-row incident">
        <div class="log-head"><strong>GET /checkout → {{ text(record(item.sample).status) }}</strong><span>{{ text(record(record(record(item.result).answers).verdict).choice) }}</span></div>
        <p>{{ JSON.stringify(record(item.sample).body) }}</p>
        <details><summary>Response and decision</summary><pre>{{ JSON.stringify(item, null, 2) }}</pre></details>
      </article>
      <details v-if="gitops.verification"><summary>Post-merge application verification</summary><pre>{{ JSON.stringify(gitops.verification, null, 2) }}</pre></details>
    </template>
    <template v-else>
    <div class="panel-heading"><h2>Live synthetic logs</h2></div>
    <p class="hint">The original checkout demo runs in Kubernetes. Jev judges its log rows; code opens an incident after three matching incident judgments.</p>
    <div class="classifier-status">
      <strong>{{ text(classifier.provider) }} · {{ text(classifier.model) }}</strong>
      <span>{{ text(classifier.status) }}</span>
      <span>{{ text(classifier.requests) }} / {{ text(classifier.maxRequests) }} requests</span>
    </div>
    <small>Native controller {{ text(connection.status) }} · observed {{ text(connection.observed_at) }}</small>
    <p v-if="nativeError.message" class="message-error">{{ text(nativeError.message) }}</p>
    <p v-if="classifier.error" class="message-error">{{ text(classifier.error) }}</p>
    <div v-if="trigger.fingerprint" class="trigger-proof">
      <strong>Incident dispatched automatically</strong>
      <span>{{ text(trigger.classifier) }} · {{ text(trigger.fingerprint) }}</span>
      <span>Matched log IDs: {{ JSON.stringify(trigger.logIds) }}</span>
      <span>Native workflow: {{ text(proactive.phase) }}</span>
    </div>
    <p class="hint">{{ text(proactive.modelMode) }}</p>
    <details><summary>POC scope</summary><p class="hint">{{ text(proactive.scope) }}</p></details>
    <article v-for="row in rows" :key="text(row.id)" class="log-row" :class="text(row.decision)">
      <div class="log-head"><strong>#{{ text(row.id) }} {{ text(row.service) }}</strong><span>{{ text(row.decision) || text(row.classification) }}</span></div>
      <small>{{ text(row.at) }} · {{ text(row.severity) }} · {{ text(row.revision) }}</small>
      <p>{{ text(row.message) }}</p>
      <details><summary>Entry and judgment</summary><pre>{{ JSON.stringify(row, null, 2) }}</pre></details>
    </article>
    </template>
  </section>
</template>

<style scoped>
.classifier-status, .trigger-proof { display: grid; gap: .4rem; padding: .8rem; margin: 1rem 0; border: 1px solid var(--line); border-radius: .6rem; font-size: .8rem; }
.trigger-proof { border-color: #d8aa43; }
.log-row { border-left: 3px solid #546258; padding: .65rem .8rem; margin-top: .8rem; background: #ffffff05; font-size: .8rem; overflow-wrap: anywhere; }
.log-row.incident { border-color: #ff7189; }
.log-row.suspicious { border-color: #d8aa43; }
.log-head { display: flex; justify-content: space-between; gap: .5rem; }
small { opacity: .7; }
p { margin: .6rem 0; }
pre { white-space: pre-wrap; max-height: 25rem; overflow: auto; font-size: .7rem; }
summary { cursor: pointer; }
</style>
