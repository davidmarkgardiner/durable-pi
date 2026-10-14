<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ArrowUp, ChevronDown, Clock3, Octagon, X } from "lucide-vue-next";
import type { WhenBusy } from "@sdk/api";
import { newId } from "../client/ids";
import { availableCommands, parseCommand, type SlashCommand } from "../client/commands";
import {
  agentHandle,
  agentState,
  attempt,
  busy,
  interrupt,
  interrupting,
  online,
  selected,
  ui,
  detail,
  deviceFeed,
} from "../client/store";

const mode = ref<WhenBusy>("followUp");
const pending = ref(false);
const nativeChat = computed(() => detail.value?.interaction?.kind === "native-chat");
const nativeBudget = computed(() => {
  const value = deviceFeed.sharedState.value?.value;
  if (!value || typeof value !== "object" || !("nativeChat" in value)) return undefined;
  const chat = value.nativeChat;
  if (!chat || typeof chat !== "object" || !("budget" in chat)) return undefined;
  const budget = chat.budget;
  if (!budget || typeof budget !== "object" || !("calls" in budget) || !("reported_tokens" in budget)) return undefined;
  return typeof budget.calls === "number" && typeof budget.reported_tokens === "number"
    ? { calls: budget.calls, tokens: budget.reported_tokens } : undefined;
});

// Typing "/" lists the slash commands; arrows pick, Tab or Enter completes.
const menuIndex = ref(0);
const menuClosed = ref(false);
const matches = computed(() => {
  const m = ui.composer.match(/^\/(\S*)$/);
  return m && !menuClosed.value
    ? availableCommands.value.filter((c) => c.name.startsWith(m[1].toLowerCase()))
    : [];
});
watch(
  () => ui.composer,
  () => {
    menuIndex.value = 0;
    if (!ui.composer.startsWith("/")) menuClosed.value = false;
  },
);
// Enter on a fully typed name runs it unless it needs an argument; otherwise the name completes.
async function pick(command: SlashCommand, enter = false) {
  const runNow =
    !command.args || (enter && command.args.startsWith("[") && ui.composer === `/${command.name}`);
  if (!runNow) ui.composer = `/${command.name} `;
  else {
    ui.composer = `/${command.name}`;
    await send();
  }
}
function keydown(e: KeyboardEvent) {
  if (!matches.value.length) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      void send();
    }
    return;
  }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    const n = matches.value.length;
    menuIndex.value = (menuIndex.value + (e.key === "ArrowDown" ? 1 : n - 1)) % n;
  } else if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey))
    void pick(matches.value[menuIndex.value], e.key === "Enter");
  else if (e.key === "Escape") menuClosed.value = true;
  else return;
  e.preventDefault();
  e.stopPropagation();
}

async function runCommand(text: string) {
  const parsed = parseCommand(text, availableCommands.value);
  if (!parsed) {
    if (nativeChat.value) {
      await attempt(async () => { throw Error("Unsupported native command. Type / to see this workspace's commands."); });
      return true;
    }
    return false;
  }
  pending.value = true;
  await attempt(async () => {
    await parsed.command.run(parsed.arg);
    ui.composer = "";
  });
  pending.value = false;
  return true;
}

// A retried send (same agent, text and mode) reuses its requestId, so the device admits it once.
async function send() {
  const content = ui.composer.trim();
  const handle = agentHandle.value;
  if (!content || pending.value || !handle) return;
  if (content.startsWith("/") && (await runCommand(content))) return;
  pending.value = true;
  const t = selected.value!;
  const key = `${t.deviceId}/${t.sessionId}/${t.agentId}`;
  let saved: { key: string; content: string; mode: string; requestId: string } | undefined;
  try {
    saved = JSON.parse(sessionStorage.getItem("dpi.pending-send") ?? "null");
  } catch {}
  const sendMode = nativeChat.value ? "reject" : mode.value;
  const requestId =
    saved?.key === key && saved.content === content && saved.mode === sendMode
      ? saved.requestId
      : newId();
  sessionStorage.setItem(
    "dpi.pending-send",
    JSON.stringify({ key, content, mode: sendMode, requestId }),
  );
  await attempt(async () => {
    await handle.send(content, sendMode, requestId);
    sessionStorage.removeItem("dpi.pending-send");
    ui.composer = "";
  });
  pending.value = false;
}

function withdraw(id: number) {
  void attempt(() => agentHandle.value!.withdraw(id));
}
</script>

<template>
  <div class="composer-region">
    <div v-if="agentState.inbox.length" class="queue">
      <div v-for="item in agentState.inbox" :key="item.id">
        <Clock3 :size="18" /><span
          >{{ item.mode === "steer" ? "Steer" : "Queued" }}:
          {{ item.content ?? "Context update" }}</span
        ><button
          class="icon-button"
          :aria-label="`Withdraw submission ${item.id}`"
          title="Withdraw queued input"
          @click="withdraw(item.id)"
        >
          <X :size="18" />
        </button>
      </div>
    </div>
    <div class="composer">
      <ul v-if="matches.length" class="slash-menu" role="listbox" aria-label="Slash commands">
        <li
          v-for="(c, i) in matches"
          :key="c.name"
          role="option"
          :aria-selected="i === menuIndex"
          :class="{ active: i === menuIndex }"
          @mousedown.prevent="pick(c)"
        >
          <code>/{{ c.name }}</code
          ><span v-if="c.args" class="slash-args">{{ c.args }}</span
          ><span class="slash-desc">{{ c.description }}</span>
        </li>
      </ul>
      <textarea
        v-model="ui.composer"
        rows="2"
        placeholder="Give your agent something to do, or type / for commands…"
        aria-label="Message your agent"
        @keydown="keydown"
      />
      <div class="composer-toolbar">
        <div class="composer-left">
          <span v-if="nativeChat" class="hint">{{ busy ? "Native agent is working" : "Live native kagent" }} · one task at a time</span>
          <div v-else class="queue-mode">
            <select
              v-model="mode"
              aria-label="When busy"
              title="Follow-up waits for this run. Steer joins after a tool round."
            >
              <option value="followUp">Follow-up</option>
              <option value="steer">Steer</option>
              <option value="reject">Reject if busy</option></select
            ><ChevronDown :size="24" aria-hidden="true" />
          </div>
        </div>
        <div class="composer-right">
          <button
            v-if="!nativeChat"
            class="interrupt"
            :disabled="!busy || interrupting"
            title="Stop foreground work and owned subagents (Escape). Background jobs continue."
            @click="interrupt"
          >
            <Octagon :size="24" class="stop-sign" fill="currentColor" />Interrupt</button
          ><button
            class="send"
            aria-label="Send message"
            :disabled="!ui.composer.trim() || pending || !agentState.ready || !online || (nativeChat && busy && !ui.composer.startsWith('/'))"
            @click="send"
          >
            <ArrowUp :size="20" />
          </button>
        </div>
      </div>
    </div>
    <div class="composer-footnote">
      <span v-if="nativeChat && detail?.interaction?.kind === 'native-chat'"><i class="live-dot" />Live Kimi · read-only incident tools · {{ nativeBudget?.calls ?? '…' }}/{{ detail.interaction.maxCalls }} model requests · {{ nativeBudget?.tokens ?? '…' }}/{{ detail.interaction.tokenBudget }} reported tokens. Closing the browser leaves native work running.</span>
      <span v-else><i class="live-dot" />Closing this window never interrupts your agent.</span>
    </div>
  </div>
</template>
