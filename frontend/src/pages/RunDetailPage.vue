<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">运行 #{{ id }}</h1>
        <p class="page-kicker">{{ run?.challenge_name ?? run?.challenge_id ?? '解题执行' }}</p>
      </div>
      <div class="actions">
        <RouterLink class="btn" to="/runs">
          <ArrowLeft :size="16" />
          运行
        </RouterLink>
        <button class="btn danger" type="button" :disabled="!canCancel || cancelling" @click="cancel">
          <Square :size="16" />
          {{ cancelling ? '取消中' : '取消运行' }}
        </button>
        <button class="btn danger" type="button" :disabled="deleting || Boolean(run && canCancel)" @click="deleteRun">
          <Trash2 :size="16" />
          {{ deleting ? '删除中' : '删除记录' }}
        </button>
      </div>
    </header>

    <p v-if="error" class="notice error">{{ error }}</p>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">运行信息</h2>
        <span v-if="run" class="status-badge" :class="statusClass(run.status)">{{ runStatusLabel(run.status) }}</span>
      </div>
      <div class="panel-body">
        <div v-if="run" class="meta-list">
          <div class="meta-item">
            <span>题目</span>
            <strong>{{ run.challenge_name ?? run.challenge_id ?? '-' }}</strong>
          </div>
          <div class="meta-item">
            <span>模型</span>
            <strong class="mono">{{ (run.model_specs ?? []).join(', ') || '-' }}</strong>
          </div>
          <div class="meta-item">
            <span>不提交 flag</span>
            <strong>{{ run.no_submit ? '开启' : '关闭' }}</strong>
          </div>
          <div class="meta-item">
            <span>生成 Writeup</span>
            <strong>{{ run.generate_writeup === false ? '关闭' : '开启' }}</strong>
          </div>
          <div class="meta-item">
            <span>费用</span>
            <strong>{{ formatRunCost(run.cost_usd) }}</strong>
          </div>
          <div class="meta-item">
            <span>创建时间</span>
            <strong>{{ formatDate(run.created_at) }}</strong>
          </div>
          <div class="meta-item">
            <span>开始时间</span>
            <strong>{{ formatDate(run.started_at) }}</strong>
          </div>
          <div class="meta-item">
            <span>结束时间</span>
            <strong>{{ formatDate(run.finished_at) }}</strong>
          </div>
          <div class="meta-item">
            <span>Flag</span>
            <strong class="mono">{{ run.result_flag ?? run.flag ?? '-' }}</strong>
          </div>
          <div class="meta-item">
            <span>获胜 Agent</span>
            <strong class="mono">{{ run.winning_agent ?? '-' }}</strong>
          </div>
          <div class="meta-item meta-item-wide">
            <span>启用 Skills</span>
            <div
              v-if="enabledSkills.length"
              class="skills-collapse"
              :class="{ expanded: skillsExpanded }"
            >
              <span v-for="skill in enabledSkills" :key="skill" class="skill-pill mono">{{ skill }}</span>
            </div>
            <strong v-else class="mono">-</strong>
            <button
              v-if="canToggleSkills"
              class="inline-action"
              type="button"
              @click="skillsExpanded = !skillsExpanded"
            >
              <ChevronUp v-if="skillsExpanded" :size="14" />
              <ChevronDown v-else :size="14" />
              {{ skillsExpanded ? '收起 Skills' : `展开全部 ${enabledSkills.length} 个 Skills` }}
            </button>
          </div>
          <div class="meta-item">
            <span>Agent 会话</span>
            <strong>{{ run.agent_session_available ? '可继续提问' : '不可用' }}</strong>
          </div>
        </div>
        <p v-else class="muted">正在加载运行信息...</p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">运行日志</h2>
          <span class="panel-kicker">{{ isLiveLog ? '实时日志' : '历史日志' }}</span>
        </div>
        <div class="actions">
          <button v-if="!isLiveLog" class="btn" type="button" :disabled="loadingLog" @click="loadLog">
            <RefreshCw :size="16" />
            刷新日志
          </button>
          <button v-if="!isLiveLog" class="btn danger" type="button" :disabled="clearingLog" @click="clearLog">
            <Trash2 :size="16" />
            {{ clearingLog ? '清空中' : '清空日志' }}
          </button>
        </div>
      </div>
      <div class="panel-body">
        <RunLogViewer v-if="isLiveLog" :run-id="id" @status="handleStreamStatus" />
        <pre v-else class="log-viewer log-viewer-compact">{{ runLog?.content || '暂无历史日志。' }}</pre>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">Writeup</h2>
        <div class="actions">
          <button class="btn" type="button" :disabled="loadingWriteup" @click="loadWriteup">
            <RefreshCw :size="16" />
            刷新
          </button>
          <a v-if="writeup?.available" class="btn primary" :href="downloadUrl">
            <Download :size="16" />
            下载 Markdown
          </a>
        </div>
      </div>
      <div class="panel-body">
        <MarkdownRenderer
          :content="writeup?.content || ''"
          empty-text="解出题目后会在这里生成 Markdown writeup。"
        />
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">向获胜 Agent 提问</h2>
        <span class="panel-kicker">{{ chat?.available ? (chat.model || 'agent') : '会话不可用' }}</span>
      </div>
      <div class="panel-body">
        <div class="chat-box">
          <div v-if="chatMessages.length" class="chat-messages">
            <article v-for="(message, index) in chatMessages" :key="index" class="chat-message" :class="`chat-${message.role}`">
              <span>{{ message.role === 'user' ? '你' : 'Agent' }}</span>
              <MarkdownRenderer :content="message.content" compact />
            </article>
          </div>
          <p v-else class="muted">如果获胜 agent 会话仍在当前后端进程内，可以在这里围绕 writeup 继续追问。</p>

          <form class="chat-form" @submit.prevent="sendChat">
            <textarea v-model="chatDraft" :disabled="!canChat || chatting" placeholder="例如：这一步为什么要泄露 libc？" />
            <button class="btn primary" type="submit" :disabled="!canChat || chatting || !chatDraft.trim()">
              <Send :size="16" />
              {{ chatting ? '发送中' : '发送' }}
            </button>
          </form>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">最终结果</h2>
      </div>
      <div class="panel-body">
        <div v-if="run" class="result-panel">
          <strong>{{ run.result_flag || run.flag ? '已找到 Flag' : '结果摘要' }}</strong>
          <pre>{{ resultText }}</pre>
        </div>
        <p v-else class="muted">暂无运行数据。</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, ChevronDown, ChevronUp, Download, RefreshCw, Send, Square, Trash2 } from 'lucide-vue-next';

import MarkdownRenderer from '@/components/MarkdownRenderer.vue';
import RunLogViewer from '@/components/RunLogViewer.vue';
import {
  api,
  canCancelRun,
  formatRunCost,
  runStatusLabel,
  runSummary,
  type AgentChat,
  type AgentChatMessage,
  type Run,
  type RunLog,
  type RunWriteup,
} from '@/lib/api';

const props = defineProps<{
  id: string;
}>();

const router = useRouter();
const run = ref<Run | null>(null);
const runLog = ref<RunLog | null>(null);
const writeup = ref<RunWriteup | null>(null);
const chat = ref<AgentChat | null>(null);
const chatDraft = ref('');
const loading = ref(false);
const loadingLog = ref(false);
const loadingWriteup = ref(false);
const clearingLog = ref(false);
const cancelling = ref(false);
const deleting = ref(false);
const chatting = ref(false);
const skillsExpanded = ref(false);
const error = ref('');

const canCancel = computed(() => Boolean(run.value && canCancelRun(run.value)));
const isLiveLog = computed(() => Boolean(run.value && !['succeeded', 'failed', 'cancelled', 'interrupted'].includes(run.value.status)));
const canChat = computed(() => Boolean(chat.value?.available || run.value?.agent_session_available));
const chatMessages = computed<AgentChatMessage[]>(() => chat.value?.messages ?? []);
const enabledSkills = computed(() => run.value?.agent_skills ?? []);
const canToggleSkills = computed(() => enabledSkills.value.length > 8 || enabledSkills.value.join(', ').length > 180);
const downloadUrl = computed(() => `/api/runs/${props.id}/writeup/download`);
const resultText = computed(() => {
  if (!run.value) return '';
  if (run.value.result) return JSON.stringify(run.value.result, null, 2);
  return runSummary(run.value);
});

function statusClass(status: string) {
  return `status-${status}`;
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
}

function mergeRun(update: Partial<Run>) {
  run.value = { ...(run.value ?? { id: props.id, status: 'queued' }), ...update };
}

function handleStreamStatus(status: unknown) {
  if (typeof status === 'string') {
    mergeRun({ status });
  } else if (status && typeof status === 'object') {
    mergeRun(status as Partial<Run>);
    const nextStatus = (status as Partial<Run>).status;
    if (nextStatus && ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(nextStatus)) {
      loadArtifacts(true);
    }
  }
}

async function load() {
  loading.value = true;
  error.value = '';
  try {
    run.value = await api.getRun(props.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载运行信息失败。';
  } finally {
    loading.value = false;
  }
}

async function loadLog() {
  loadingLog.value = true;
  error.value = '';
  try {
    runLog.value = await api.getRunLog(props.id, 1200);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载历史日志失败。';
  } finally {
    loadingLog.value = false;
  }
}

async function clearLog() {
  clearingLog.value = true;
  error.value = '';
  try {
    runLog.value = await api.clearRunLog(props.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '清空历史日志失败。';
  } finally {
    clearingLog.value = false;
  }
}

async function loadWriteup() {
  loadingWriteup.value = true;
  error.value = '';
  try {
    writeup.value = await api.getWriteup(props.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载 writeup 失败。';
  } finally {
    loadingWriteup.value = false;
  }
}

async function loadChat() {
  try {
    chat.value = await api.getAgentMessages(props.id);
  } catch {
    chat.value = { run_id: props.id, available: false, messages: [] };
  }
}

async function loadArtifacts(includeLog = false) {
  await Promise.all([includeLog ? loadLog() : Promise.resolve(), loadWriteup(), loadChat()]);
}

async function cancel() {
  if (!canCancel.value) return;
  cancelling.value = true;
  error.value = '';
  try {
    run.value = await api.cancelRun(props.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '取消运行失败。';
  } finally {
    cancelling.value = false;
  }
}

async function deleteRun() {
  if (canCancel.value) return;
  if (!window.confirm(`确认删除运行 #${props.id} 的历史记录和关联日志？`)) return;
  deleting.value = true;
  error.value = '';
  try {
    await api.deleteRun(props.id);
    await router.push('/runs');
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除运行记录失败。';
  } finally {
    deleting.value = false;
  }
}

async function sendChat() {
  const message = chatDraft.value.trim();
  if (!message || !canChat.value) return;
  chatting.value = true;
  error.value = '';
  try {
    chat.value = await api.askAgent(props.id, message);
    chatDraft.value = '';
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Agent 问答失败。';
  } finally {
    chatting.value = false;
  }
}

onMounted(async () => {
  await load();
  await loadArtifacts(!isLiveLog.value);
});
</script>
