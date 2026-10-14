<script setup lang="ts">
import { computed } from "vue";
import { Check, ChevronRight, FileText, Wrench } from "lucide-vue-next";
import type { JobRun } from "@sdk/jobs";
import type { TranscriptItem, ToolCallView } from "@sdk/transcript";
import { markdown } from "../client/markdown";
import JobCard from "./JobCard.vue";
import IncidentHandoff from "./IncidentHandoff.vue";
import { pending, startIncident } from "../client/jobs";

const props = defineProps<{ run: JobRun; items: TranscriptItem[] }>();
const emit = defineEmits<{ transcript: [] }>();
const calls = computed(() => props.items.flatMap((item): ToolCallView[] => {
  if (item.kind === "tool") return [item.call];
  if (item.kind === "assistant") return item.blocks.flatMap((block) => block.type === "tool" ? [block.call] : []);
  return [];
}));
const report = computed(() => props.items.flatMap((item) => item.kind === "assistant"
  ? item.blocks.flatMap((block) => block.type === "text" ? [block.text] : []) : []).at(-1));
const setupFailure = computed(() => props.items.some((item) => item.kind === "event" && item.text.startsWith("Native task failed:")));
const summary = computed(() => props.run.decisionSummary);

function receipt(text: string): string {
  try {
    let value: unknown = JSON.parse(text);
    if (typeof value === "object" && value !== null && "output" in value && typeof value.output === "string") {
      value = JSON.parse(value.output);
    }
    return JSON.stringify(value, null, 2);
  } catch {
    return text;
  }
}
</script>

<template>
  <section class="workflow-results" aria-label="Workflow results">
    <header class="results-heading">
      <div><span class="eyebrow">APPLICATION REMEDIATION</span><h2>{{ run.status === 'completed' ? 'Guest checkout restored' : run.status === 'waiting' ? 'Rollback ready for your decision' : 'Checkout investigation' }}</h2></div>
      <span class="results-source">Live native kagent</span>
    </header>
    <p class="results-about">Guided application specialist · real Kubernetes and GitLab tools · human merge approval</p>
    <div v-if="run.canStartIncident" class="outcome-summary">
      <p>Start one synthetic incident by committing the configured faulty image to this demo repository. Flux deploys it. A scripted decision rule detects three failed checkout requests and hands the incident to the native specialist.</p>
      <button class="text-button" :disabled="Boolean(pending)" @click="startIncident(run)">Start synthetic incident</button>
    </div>
    <IncidentHandoff v-if="run.incidentHandoff" :handoff="run.incidentHandoff" />
    <div v-if="run.status === 'completed'" class="recovery-result" role="status">
      <Check :size="22" /><div><strong>Application verification passed</strong><p>The agent verified the merged commit, Flux rollout, image v1 and three successful checkout requests.</p></div>
    </div>
    <JobCard :run="run" compact />
    <div v-if="summary && run.approval !== 'pending'" class="outcome-summary">
      <div><span class="result-label">Agent finding</span><p>{{ summary.cause }}</p></div>
      <div><span class="result-label">Remediation</span><p>{{ summary.change }}</p></div>
      <div><span class="result-label">Review</span><p>{{ summary.review }}</p></div>
      <div class="result-links">
        <a v-if="summary.mergeRequestUrl" :href="summary.mergeRequestUrl" target="_blank" rel="noopener noreferrer">GitLab merge request <ChevronRight :size="15" /></a>
        <a v-if="summary.pipelineUrl" :href="summary.pipelineUrl" target="_blank" rel="noopener noreferrer">Successful CI pipeline <ChevronRight :size="15" /></a>
      </div>
    </div>
    <details v-if="report" class="agent-report" :open="run.status === 'completed'">
      <summary><FileText :size="17" />Agent's {{ run.status === 'completed' ? 'final report' : 'latest report' }}</summary>
      <div class="markdown" v-html="markdown(report)" />
    </details>
    <details class="tool-receipts">
      <summary><Wrench :size="17" />MCP tool results <span>{{ calls.filter(call => call.status === 'done').length }} completed</span></summary>
      <details v-for="call in calls" :key="call.callId" class="result-tool">
        <summary><Check v-if="call.status === 'done'" :size="15" /><code>{{ call.name }}</code><span>{{ call.status }}</span></summary>
        <div class="result-label">Tool input</div><pre>{{ JSON.stringify(call.args, null, 2) }}</pre>
        <template v-if="call.result"><div class="result-label">Recorded tool result</div><pre>{{ receipt(call.result) }}</pre></template>
      </details>
    </details>
    <p v-if="setupFailure" class="setup-note">An earlier gateway request failed during setup. The full transcript retains that failure and the continuation.</p>
    <button class="text-button transcript-link" @click="emit('transcript')">Open full agent transcript <ChevronRight :size="16" /></button>
  </section>
</template>

<style scoped>
.workflow-results { width: min(100%, 900px); padding: 26px 24px 36px; margin: 0 auto; }
.results-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.results-heading h2 { font-size: 25px; margin-top: 7px; }
.results-source { flex-shrink: 0; font-size: 12px; color: var(--muted); border: 1px solid var(--line); border-radius: 20px; padding: 7px 11px; }
.results-about { color: var(--muted); font-size: 13px; line-height: 1.6; margin: 12px 0 22px; }
.recovery-result { display: flex; gap: 12px; padding: 16px; border: 1px solid #486852; border-radius: 10px; background: #193d2529; margin-bottom: 18px; }
.recovery-result svg { color: #a5dab4; flex-shrink: 0; }
.recovery-result p { margin-top: 5px; color: #d1e3d6; font-size: 13px; line-height: 1.5; }
.outcome-summary { display: grid; gap: 16px; padding: 18px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; margin: 18px 0; }
.result-label { font-size: 11px; color: var(--muted); letter-spacing: .04em; }
.outcome-summary p { margin-top: 5px; font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; }
.result-links { display: flex; flex-wrap: wrap; gap: 18px; }
.result-links a { display: inline-flex; align-items: center; color: var(--accent); font-size: 13px; text-underline-offset: 3px; }
.agent-report, .tool-receipts { border: 1px solid var(--line); border-radius: 10px; margin-top: 18px; padding: 14px 16px; }
summary { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; }
summary span { margin-left: auto; font-size: 12px; color: var(--muted); }
.agent-report .markdown { margin-top: 16px; }
.result-tool { padding: 14px 0; border-bottom: 1px solid var(--line); }
.result-tool:last-child { border-bottom: 0; }
.result-tool .result-label { margin-top: 15px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 11px; line-height: 1.6; max-height: 350px; overflow: auto; }
.setup-note { color: var(--muted); font-size: 12px; line-height: 1.6; margin-top: 18px; }
.transcript-link { margin-top: 14px; }
@media (max-width: 650px) { .workflow-results { padding: 18px 14px; } .results-heading { align-items: flex-start; flex-direction: column; } .results-heading h2 { font-size: 21px; } }
</style>
