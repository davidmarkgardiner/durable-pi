<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  Activity,
  Braces,
  ChevronDown,
  FolderOpen,
  Pencil,
  Server,
  ShieldCheck,
  Wrench,
  PanelLeftClose,
  PanelLeftOpen,
  Puzzle,
} from "lucide-vue-next";
import { THINKING_LEVELS, type ThinkingLevel } from "@sdk/api";
import type { StateChange } from "@sdk/app-state";
import StateEditor from "./StateEditor.vue";
import LogsPanel from "./LogsPanel.vue";
import CapabilitiesPanel from "./CapabilitiesPanel.vue";
import TasksPanel from "./TasksPanel.vue";
import ExtensionsPanel from "./ExtensionsPanel.vue";
import ContextBar from "./ContextBar.vue";
import { message } from "../client/hub";
import { toolSignature } from "../client/signature";
import {
  agentHandle,
  agentState,
  attempt,
  busy,
  currentModel,
  detail,
  device,
  deviceFeed,
  hideInspector,
  icon,
  inspectorExpanded,
  json,
  notify,
  number,
  refreshDetail,
  session,
  sessionHandle,
  sessionSummary,
  showInspector,
  tasks,
  ui,
  usage,
  panelKeys,
} from "../client/store";

// Each tool's parameters as a highlighted TypeScript declaration, rebuilt only when the tools change.
const signatures = computed(
  () => new Map(detail.value?.tools.map((t) => [t.name, toolSignature(t.name, t.parameters)])),
);

const tabs = computed(() => [
  { id: "session", label: "Session", icon: FolderOpen },
  { id: "state", label: "State", icon: Braces },
  { id: "tasks", label: "Tasks", icon: Activity },
  { id: "tools", label: "Tools", icon: Wrench },
  ...(device.value?.info?.capabilities.includes("agent-capabilities") ? [
    { id: "skills", label: "Skills", icon: Puzzle },
    { id: "models", label: "Models", icon: Server },
  ] : []),
  { id: "extensions", label: "Extend", icon: Puzzle },
  ...(device.value?.info?.capabilities.includes("logs") ? [{ id: "logs", label: "Logs", icon: Activity }] : []),
]);
const usageRows = computed(() => [
  { label: "Input", tokens: usage.value.input, cost: usage.value.inputCost },
  { label: "Output", tokens: usage.value.output, cost: usage.value.outputCost },
  { label: "Cache read", tokens: usage.value.cacheRead, cost: usage.value.cacheReadCost },
  { label: "Cache write", tokens: usage.value.cacheWrite, cost: usage.value.cacheWriteCost },
]);
const background = computed(() => tasks.value.filter((t) => t.background).length);

function configure(
  patch: Parameters<NonNullable<typeof agentHandle.value>["configure"]>[0],
  done?: string,
) {
  if (device.value?.info?.clientControls?.configure === false) return;
  void attempt(async () => {
    await agentHandle.value!.configure(patch);
    await refreshDetail();
    if (done) notify(done);
  });
}

function renameSession() {
  const handle = sessionHandle.value;
  if (!handle) return;
  ui.dialog = {
    kind: "prompt",
    title: "Rename session",
    label: "Session name",
    value: sessionSummary.value?.name ?? "",
    submit: "Save name",
    run: (name) => handle.rename(name),
  };
}

// ------------------------------------------------------------ App State (device-wide document)

const shared = deviceFeed.sharedState;
const stateDraft = ref("");
const stateBaseline = ref("");
const stateDraftRevision = ref(0);
const stateSaving = ref(false);
const stateError = ref("");
const stateDirty = computed(() => stateDraft.value !== stateBaseline.value);
const stateConflict = computed(
  () => stateDirty.value && shared.value?.revision !== stateDraftRevision.value,
);
function resetStateDraft() {
  stateDraft.value = json(shared.value?.value ?? {});
  stateBaseline.value = stateDraft.value;
  stateDraftRevision.value = shared.value?.revision ?? 0;
  stateError.value = "";
}
watch(shared, () => !stateDirty.value && resetStateDraft(), { immediate: true });

async function editState(change: StateChange) {
  if (stateSaving.value || !agentHandle.value) return;
  stateSaving.value = true;
  stateError.value = "";
  try {
    await agentHandle.value.demo("state", change);
  } catch (e) {
    stateError.value = message(e);
  } finally {
    stateSaving.value = false;
  }
}
async function saveStateJson() {
  if (stateSaving.value || !agentHandle.value) return;
  stateError.value = "";
  stateSaving.value = true;
  try {
    const value = JSON.parse(stateDraft.value);
    if (!value || Array.isArray(value) || typeof value !== "object")
      throw Error("App State must be a JSON object.");
    const saved = await agentHandle.value.demo<{ value: unknown; revision: number }>("state", {
      operation: "update",
      path: "",
      value,
      expectedRevision: stateDraftRevision.value,
    });
    stateDraft.value = json(saved.value);
    stateBaseline.value = stateDraft.value;
    stateDraftRevision.value = saved.revision;
    notify("Shared App State saved.");
  } catch (e) {
    stateError.value = message(e);
  } finally {
    stateSaving.value = false;
  }
}

const stateEditable = computed(() => device.value?.info?.capabilities.includes("demo") !== false);
const configurable = computed(() => device.value?.info?.clientControls?.configure !== false);
const readOnly = computed(() => detail.value?.config.readOnly === true);
const offeredTools = computed(() => detail.value?.tools.filter((t) => t.offered).length ?? 0);
</script>

<template>
  <aside class="inspector" :class="{ collapsed: !inspectorExpanded, overlay: ui.inspectorOverlay }">
    <div v-if="!inspectorExpanded" class="panel-rail" aria-label="Inspector (collapsed)">
      <button
        class="icon-button panel-toggle"
        aria-label="Expand inspector"
        :title="`Expand inspector (${panelKeys.inspector})`"
        @click="showInspector()"
      >
        <PanelLeftOpen :size="18" />
      </button>
      <button
        v-for="t in tabs"
        :key="t.id"
        class="rail-tab"
        :class="{ active: ui.tab === t.id }"
        :aria-label="`Open ${t.label}`"
        :title="t.label"
        @click="showInspector(t.id)"
      >
        <component :is="t.icon" :size="20" /><span
          v-if="t.id === 'tasks' && tasks.length"
          class="count"
          >{{ tasks.length }}</span
        >
      </button>
    </div>
    <template v-else>
      <div class="inspector-tabs" :class="{ 'with-capabilities': device?.info?.capabilities.includes('agent-capabilities') }" role="tablist" aria-label="Session details">
        <button
          v-for="t in tabs"
          :id="`inspector-tab-${t.id}`"
          :key="t.id"
          role="tab"
          aria-controls="inspector-panel"
          :aria-selected="ui.tab === t.id"
          :class="{ active: ui.tab === t.id }"
          @click="ui.tab = t.id"
        >
          <component :is="t.icon" :size="18" />{{ t.label
          }}<span v-if="t.id === 'tasks' && tasks.length" class="count">{{ tasks.length }}</span>
        </button>
        <button
          class="icon-button panel-toggle"
          aria-label="Collapse inspector"
          :title="`Collapse inspector (${panelKeys.inspector})`"
          @click="hideInspector()"
        >
          <PanelLeftClose :size="18" />
        </button>
      </div>
      <div
        id="inspector-panel"
        class="inspector-body"
        :class="{ 'session-panel': ui.tab === 'session' }"
        role="tabpanel"
        :aria-labelledby="`inspector-tab-${ui.tab}`"
      >
        <template v-if="ui.tab === 'session'">
          <section class="session-heading">
            <h1>
              <span>{{ sessionSummary?.name ?? "Loading session" }}</span
              ><button
                class="icon-button"
                title="Rename session"
                aria-label="Rename session"
                @click="renameSession"
              >
                <Pencil :size="18" />
              </button>
            </h1>
            <button
              class="path cwd-button"
              :title="sessionSummary?.cwd"
              aria-label="Show full working directory"
              @click="ui.dialog = { kind: 'path', path: sessionSummary?.cwd ?? '' }"
            >
              <FolderOpen :size="18" /><span class="cwd-trail" dir="rtl"
                ><bdi dir="ltr">{{ sessionSummary?.cwd }}</bdi></span
              >
            </button>
            <div class="session-status">
              <span class="status-pill" :class="{ working: busy }"
                ><i />{{ busy ? "Working" : "Idle" }}</span
              ><span v-if="background" class="background-pill">{{ background }} background</span
              ><span class="saved"><Server :size="18" />{{ device?.id }}</span>
            </div>
          </section>
          <section class="model-section">
            <div class="section-label">
              <span>AGENT</span>
            </div>
            <button :disabled="!configurable" class="model-button" @click="ui.dialog = { kind: 'models' }">
              <img :src="icon(agentState.agent.model?.modelId)" alt="" />
              <div>
                <strong>{{
                  currentModel?.name ?? agentState.agent.model?.modelId ?? "Loading…"
                }}</strong
                ><small
                  >{{ currentModel?.tier ?? "" }} /
                  {{ agentState.agent.model?.provider ?? "" }}</small
                >
              </div>
              <ChevronDown :size="18" />
            </button>
            <div class="thinking-row">
              <span>Thinking</span
              ><select
                aria-label="Thinking level"
                :disabled="!configurable"
                :value="agentState.agent.thinkingLevel ?? 'low'"
                @change="
                  configure(
                    { thinkingLevel: ($event.target as HTMLSelectElement).value as ThinkingLevel },
                    `Thinking ${($event.target as HTMLSelectElement).value}. Used on the next turn.`,
                  )
                "
              >
                <option v-for="level in THINKING_LEVELS" :key="level">{{ level }}</option>
              </select>
            </div>
            <ContextBar v-if="configurable" />
            <section v-if="detail?.config.model?.provider !== 'kagent'" class="stats-section" aria-labelledby="stats-title">
              <div class="section-label"><span id="stats-title">STATS</span></div>
              <div class="metrics">
                <div :title="`${usage.tokens.toLocaleString('en-US')} total tokens`">
                  <span>{{ number(usage.tokens) }}</span
                  ><small>total tokens</small>
                </div>
                <div>
                  <span>${{ usage.cost.toFixed(4) }}</span
                  ><small>agent cost</small>
                </div>
                <div>
                  <span>{{ detail?.tools.length ?? 0 }}</span
                  ><small>tools</small>
                </div>
              </div>
              <table class="usage-breakdown" aria-label="Agent token and cost breakdown">
                <thead>
                  <tr>
                    <th scope="col">Type</th>
                    <th scope="col">Tokens</th>
                    <th scope="col">Cost (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in usageRows" :key="row.label">
                    <th scope="row">{{ row.label }}</th>
                    <td>{{ row.tokens.toLocaleString("en-US") }}</td>
                    <td>${{ row.cost.toFixed(4) }}</td>
                  </tr>
                </tbody>
              </table>
            </section>
          </section>
        </template>
        <template v-if="ui.tab === 'state'">
          <div class="panel-heading">
            <h2>App State</h2>
            <Braces :size="18" />
          </div>
          <p v-if="!stateEditable" class="hint">Observed Kubernetes logs, classifications, task and actor state. This view is read only.</p>
          <pre v-if="!stateEditable" class="app-state-json">{{ stateDraft }}</pre>
          <p v-if="stateEditable" class="hint app-state-description">
            One shared JSON object for every agent, session and fork on {{ device?.id }}. You and
            your agents can read, create, update or delete values and fields. Changes appear live
            and persist across closed browsers, interrupted agents and backend restarts.
          </p>
          <textarea
            v-if="stateEditable"
            v-model="stateDraft"
            class="app-state-json"
            aria-label="App State JSON"
            spellcheck="false"
            :disabled="stateSaving || !shared"
            rows="12"
          />
          <div v-if="stateEditable" class="state-json-actions">
            <span v-if="stateConflict" class="hint"
              >State changed elsewhere. Load the latest JSON before saving.</span
            >
            <button
              v-if="stateDirty"
              class="secondary"
              :disabled="stateSaving"
              @click="resetStateDraft"
            >
              {{ stateConflict ? "Load latest" : "Reset" }}
            </button>
            <button
              class="primary small"
              :disabled="!stateDirty || stateSaving || stateConflict"
              @click="saveStateJson"
            >
              {{ stateSaving ? "Saving…" : "Save JSON" }}
            </button>
          </div>
          <p v-if="stateError" class="message-error" role="alert">{{ stateError }}</p>
          <StateEditor
            v-if="stateEditable"
            :value="shared?.value ?? {}"
            :disabled="stateSaving || stateDirty || !shared"
            @change="editState"
          />
        </template>
        <LogsPanel v-if="ui.tab === 'logs'" />
        <CapabilitiesPanel v-if="ui.tab === 'skills'" section="skills" />
        <CapabilitiesPanel v-if="ui.tab === 'models'" section="models" />
        <TasksPanel v-if="ui.tab === 'tasks'" />
        <ExtensionsPanel v-if="ui.tab === 'extensions'" />
        <template v-if="ui.tab === 'tools'"
          ><div class="panel-heading">
            <h2>Tools</h2>
            <span class="tag">{{ offeredTools }} / {{ detail?.tools.length ?? 0 }}</span>
          </div>
          <p class="hint">{{ configurable ? "Every tool this agent's extensions provide. Open one to see its definition." : "Native MCP tools selected by this agent's Kubernetes template. Descriptions come from controller discovery." }}</p>
          <p v-if="detail?.capabilityInventory" class="hint">Observed {{ detail.capabilityInventory.observedAt }}</p>
          <div class="hook-card">
            <div>
              <ShieldCheck :size="18" /><strong>Read only</strong
              ><button
                class="switch"
                role="switch"
                :aria-checked="readOnly"
                aria-label="Read only"
                :disabled="!configurable"
                :class="{ on: readOnly }"
                @click="
                  configure(
                    { readOnly: !readOnly },
                    readOnly ? 'Read only off. Every tool is back.' : 'Read only on. Tools that write are disabled.',
                  )
                "
              >
                <span />
              </button>
            </div>
            <p v-if="configurable">
              Offers this agent only tools that read. Tools that create, update or delete leave its next request, and
              the choice is stored with the agent.
            </p>
            <p v-else>The Kubernetes template owns this tool selection. This pane cannot change it.</p>
          </div>
          <details
            v-for="tool in detail?.tools"
            :key="tool.name"
            class="tool-row"
            :class="{ disabled: !tool.offered }"
          >
            <summary>
              <Wrench :size="18" /><strong>{{ tool.name }}</strong
              ><span v-if="!tool.offered" class="tag tool-disabled">disabled</span
              ><span v-if="tool.requireApproval" class="tag">Human approval</span
              ><span v-if="configurable" class="tag">{{ tool.replay === "safe" ? "replay safe" : "interrupt on crash" }}</span>
            </summary>
            <p>{{ tool.description }}</p>
            <pre
              v-if="tool.parameters"
              class="tool-signature"
              :aria-label="`${tool.name} TypeScript definition`"
            ><code><span v-for="(t, i) in signatures.get(tool.name)" :key="i" :class="`tk-${t.kind}`">{{ t.text }}</span></code></pre>
            <small v-if="!configurable">MCP server: {{ tool.server }}. Tool schemas are not included in controller discovery.</small>
            <small v-else>{{
              tool.replay === "safe"
                ? "An interrupted execution may run again after recovery."
                : "A crash records an interrupted result instead of rerunning this effect."
            }}</small>
          </details></template
        >
      </div>
    </template>
  </aside>
</template>

<style scoped>
.inspector-tabs.with-capabilities { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); position: relative; padding-right: 28px; }
.inspector-tabs.with-capabilities button[role="tab"] { padding: 10px 4px; gap: 5px; }
.inspector-tabs.with-capabilities .panel-toggle { position: absolute; right: 2px; top: 9px; }
</style>
