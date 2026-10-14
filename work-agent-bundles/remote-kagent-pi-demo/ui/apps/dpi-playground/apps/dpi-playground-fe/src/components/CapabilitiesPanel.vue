<script setup lang="ts">
import { computed } from "vue";
import { detail, refreshDetail, attempt } from "../client/store";
import { now } from "../client/jobs";

defineProps<{ section: "skills" | "models" }>();
const inventory = computed(() => detail.value?.capabilityInventory);
const stale = computed(() => !inventory.value || now.value - Date.parse(inventory.value.observedAt) > 120_000);
const selectedModels = computed(() => inventory.value?.models.filter((model) => model.selected) ?? []);
const otherModels = computed(() => inventory.value?.models.filter((model) => !model.selected) ?? []);
</script>

<template>
  <section class="capabilities-panel">
    <div class="panel-heading"><h2>{{ section === 'skills' ? 'Skills and instructions' : 'Model garden' }}</h2>
      <button class="secondary small" @click="attempt(refreshDetail)">Refresh inventory</button>
    </div>
    <p v-if="!inventory" class="hint">The Kubernetes inventory has not been collected yet.</p>
    <template v-else>
      <p class="hint">{{ inventory.cluster }}<br />Observed {{ inventory.observedAt }}</p>
      <p v-if="stale" class="message-error">Inventory is more than two minutes old. Current availability needs a fresh observation.</p>
      <template v-if="section === 'skills'">
        <p class="hint">Skills declared in this agent's template. A declared source does not by itself prove that the runtime loaded or used the skill.</p>
        <p v-if="!inventory.skills.length">No skills are declared for this agent.</p>
        <details v-for="skill in inventory.skills" :key="skill.name" class="tool-row">
          <summary><strong>{{ skill.name }}</strong></summary>
          <p class="capability-source">{{ skill.source }}</p>
        </details>
        <details class="tool-row" open>
          <summary><strong>Agent instructions</strong></summary>
          <pre>{{ inventory.instructions }}</pre>
        </details>
        <p class="hint">Template: {{ inventory.template }}<br />Harness: {{ inventory.harness }}</p>
        <details class="tool-row">
          <summary><strong>Durability and context</strong></summary>
          <p>Snapshots: {{ inventory.runtime.snapshots }}</p>
          <p>{{ inventory.runtime.compaction }}</p>
        </details>
      </template>
      <template v-else>
        <p class="hint">Configured ModelConfigs in this namespace. Selection and working provider access are separate checks. This view does not change an agent's model.</p>
        <p class="hint">Open Logs for the active incident classifier and its decision count. A scripted synthetic classifier is labelled separately from the agent model.</p>
        <details v-for="model in selectedModels" :key="model.name" class="tool-row" open>
          <summary><strong>{{ model.model }}</strong><span class="tag">Selected</span></summary>
          <p>{{ model.name }}<br />{{ model.provider }}<br />{{ model.mode }}</p>
        </details>
        <details class="tool-row">
          <summary><strong>Other configured routes</strong><span class="tag">{{ otherModels.length }}</span></summary>
          <dl class="model-routes"><template v-for="model in otherModels" :key="model.name">
            <dt>{{ model.name }}</dt><dd>{{ model.model }} · {{ model.provider }}<br />{{ model.mode }}</dd>
          </template></dl>
        </details>
      </template>
      <details class="tool-row"><summary>Inventory source</summary><p>{{ inventory.source }}</p></details>
    </template>
  </section>
</template>

<style scoped>
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.5; }
.capability-source { overflow-wrap: anywhere; }
.model-routes { overflow-wrap: anywhere; font-size: 12px; }
.model-routes dt { margin-top: 12px; font-weight: 600; }
.model-routes dd { margin: 4px 0 0; line-height: 1.5; }
</style>
