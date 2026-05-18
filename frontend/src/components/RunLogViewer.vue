<template>
  <div class="log-shell">
    <div class="log-toolbar">
      <span class="muted">{{ connectionLabel }}</span>
      <button class="btn" type="button" @click="clear">
        <Trash2 :size="16" />
        清空
      </button>
    </div>
    <pre ref="logEl" class="log-viewer">{{ logText }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { Trash2 } from 'lucide-vue-next';

import { openRunLogStream } from '@/lib/sse';

const props = defineProps<{
  runId: string | number;
}>();

const emit = defineEmits<{
  status: [status: unknown];
}>();

const lines = ref<string[]>([]);
const connected = ref(false);
const errored = ref(false);
const logEl = ref<HTMLElement | null>(null);
let source: EventSource | null = null;
let pendingLines: string[] = [];
let flushHandle = 0;
const MAX_LOG_LINES = 1000;

const logText = computed(() => lines.value.join('\n'));
const connectionLabel = computed(() => {
  if (errored.value) return '日志流已断开';
  if (connected.value) return '日志流已连接';
  return '正在连接日志流';
});

function append(line: string) {
  pendingLines.push(line);
  if (!flushHandle) {
    flushHandle = window.setTimeout(flushPendingLines, 80);
  }
}

function flushPendingLines() {
  flushHandle = 0;
  if (!pendingLines.length) return;
  const next = [...lines.value, ...pendingLines];
  pendingLines = [];
  lines.value = next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next;
}

function clear() {
  pendingLines = [];
  lines.value = [];
}

function connect() {
  close();
  errored.value = false;
  connected.value = false;
  source = openRunLogStream(props.runId, {
    onEvent(event) {
      if (event.type === 'log') {
        connected.value = true;
        append(event.data);
      } else if (event.type === 'status') {
        connected.value = true;
        emit('status', event.data);
      } else if (event.type === 'heartbeat') {
        connected.value = true;
      } else {
        errored.value = true;
      }
    },
  });
}

function close() {
  if (flushHandle) {
    window.clearTimeout(flushHandle);
    flushHandle = 0;
  }
  flushPendingLines();
  source?.close();
  source = null;
}

watch(logText, async () => {
  await nextTick();
  if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight;
});

watch(
  () => props.runId,
  () => {
    lines.value = [];
    connect();
  },
);

onMounted(connect);
onBeforeUnmount(close);
</script>
