<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">{{ metadata.name || `题目 ${id}` }}</h1>
        <p class="page-kicker mono">{{ challenge?.path ?? challenge?.challenge_dir ?? '题目信息' }}</p>
      </div>
      <div class="actions">
        <RouterLink class="btn" to="/challenges">
          <ArrowLeft :size="16" />
          题目
        </RouterLink>
        <button class="btn danger" type="button" :disabled="deleting" @click="deleteCurrentChallenge">
          <Trash2 :size="16" />
          {{ deleting ? '删除中' : '删除题目' }}
        </button>
      </div>
    </header>

    <p v-if="error" class="notice error">{{ error }}</p>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">题目信息</h2>
        <span v-if="loading" class="muted">加载中</span>
      </div>
      <div class="panel-body">
        <ChallengeForm :metadata="metadata" :saving="saving" :message="saveMessage" @save="save" />
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">附件文件</h2>
        <span class="muted">{{ distfiles.length }} 个文件</span>
      </div>
      <div class="panel-body">
        <ul v-if="distfiles.length" class="dist-list">
          <li v-for="file in distfiles" :key="file" class="mono">{{ file }}</li>
        </ul>
        <p v-else class="muted">当前题目没有附件文件。</p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">运行状态</h2>
          <span class="panel-kicker">{{ activeRuns.length }} 个活跃任务</span>
        </div>
        <button class="btn" type="button" @click="loadRuns()">
          <RefreshCw :size="16" />
          刷新状态
        </button>
      </div>
      <div class="panel-body">
        <p v-if="runError" class="notice error">{{ runError }}</p>
        <div v-if="activeRuns.length" class="run-state-grid">
          <article v-for="run in activeRuns" :key="run.id" class="run-state-card">
            <div>
              <strong>#{{ run.id }}</strong>
              <span class="status-badge" :class="statusClass(run.status)">{{ runStatusLabel(run.status) }}</span>
            </div>
            <p>{{ runSummary(run) }}</p>
            <div class="table-actions">
              <RouterLink class="btn compact" :to="`/runs/${run.id}`">
                <ScrollText :size="15" />
                日志
              </RouterLink>
              <button
                class="btn compact danger"
                type="button"
                :disabled="!canCancelRun(run) || isCancelling(run)"
                @click="cancelRun(run)"
              >
                <Square :size="15" />
                {{ isCancelling(run) ? '停止中' : '停止' }}
              </button>
            </div>
          </article>
        </div>
        <p v-else-if="runsLoading" class="muted">正在加载运行状态...</p>
        <p v-else class="muted">当前题目没有活跃运行。</p>

        <div class="table-wrap run-history-table">
          <table class="data-table">
            <thead>
              <tr>
                <th>运行</th>
                <th>状态</th>
                <th>模型</th>
                <th>开始时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="runsLoading">
                <td colspan="5" class="muted">正在加载运行记录...</td>
              </tr>
              <tr v-else-if="runs.length === 0">
                <td colspan="5" class="muted">这个题目还没有运行记录。</td>
              </tr>
              <tr v-for="run in runs" v-else :key="run.id">
                <td>
                  <RouterLink class="link-row mono" :to="`/runs/${run.id}`">#{{ run.id }}</RouterLink>
                </td>
                <td><span class="status-badge" :class="statusClass(run.status)">{{ runStatusLabel(run.status) }}</span></td>
                <td class="mono">{{ (run.model_specs ?? []).join(', ') || '-' }}</td>
                <td>{{ formatDate(run.started_at ?? run.created_at) }}</td>
                <td>
                  <div class="table-actions">
                    <RouterLink class="btn compact" :to="`/runs/${run.id}`">
                      <ScrollText :size="15" />
                      日志
                    </RouterLink>
                    <button
                      class="btn compact danger"
                      type="button"
                      :disabled="!canCancelRun(run) || isCancelling(run)"
                      @click="cancelRun(run)"
                    >
                      <Square :size="15" />
                      {{ isCancelling(run) ? '停止中' : '停止' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">启动运行</h2>
      </div>
      <div class="panel-body">
        <RunLauncherForm
          :challenge-id="id"
          :launching="launching"
          :message="launchMessage"
          :models="modelCatalog"
          default-model="openai/gpt-5.5"
          @launch="launch"
        />
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, RefreshCw, ScrollText, Square, Trash2 } from 'lucide-vue-next';

import ChallengeForm from '@/components/ChallengeForm.vue';
import RunLauncherForm from '@/components/RunLauncherForm.vue';
import {
  api,
  canCancelRun,
  challengeMeta,
  runStatusLabel,
  runSummary,
  type Challenge,
  type EditableChallengeMetadata,
  type Run,
} from '@/lib/api';

const props = defineProps<{
  id: string;
}>();

const router = useRouter();
const challenge = ref<Challenge | null>(null);
const loading = ref(false);
const saving = ref(false);
const launching = ref(false);
const deleting = ref(false);
const error = ref('');
const runError = ref('');
const saveMessage = ref('');
const launchMessage = ref('');
const runs = ref<Run[]>([]);
const runsLoading = ref(false);
const cancellingIds = ref<Set<string>>(new Set());
const modelCatalog = ref<string[]>([]);
let pollTimer: number | undefined;

const metadata = computed(() => (challenge.value ? challengeMeta(challenge.value) : {}));
const distfiles = computed(() => challenge.value?.distfiles ?? []);
const activeRuns = computed(() => runs.value.filter((run) => run.active || canCancelRun(run)));

async function load() {
  loading.value = true;
  error.value = '';
  try {
    challenge.value = await api.getChallenge(props.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载题目失败。';
  } finally {
    loading.value = false;
  }
}

async function loadModels() {
  try {
    const catalog = await api.listModels();
    modelCatalog.value = catalog.models;
  } catch {
    modelCatalog.value = [];
  }
}

async function loadRuns(silent = false) {
  if (!silent) runsLoading.value = true;
  runError.value = '';
  try {
    runs.value = await api.listRuns({ challengeId: props.id });
  } catch (err) {
    runError.value = err instanceof Error ? err.message : '加载运行状态失败。';
  } finally {
    if (!silent) runsLoading.value = false;
  }
}

async function save(nextMetadata: Partial<EditableChallengeMetadata>) {
  saving.value = true;
  saveMessage.value = '';
  error.value = '';
  try {
    challenge.value = await api.updateChallenge(props.id, nextMetadata);
    saveMessage.value = '题目信息已保存。';
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存题目信息失败。';
  } finally {
    saving.value = false;
  }
}

async function launch(payload: {
  challenge_id: number;
  model_specs?: string[];
  no_submit: boolean;
  generate_writeup: boolean;
}) {
  launching.value = true;
  launchMessage.value = '';
  error.value = '';
  try {
    const run = await api.createRun(payload);
    await router.push(`/runs/${run.id}`);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '启动运行失败。';
  } finally {
    launching.value = false;
  }
}

async function deleteCurrentChallenge() {
  const name = metadata.value.name || `题目 ${props.id}`;
  if (!window.confirm(`确认从 FlagForge 删除「${name}」？本地文件默认保留。`)) return;
  deleting.value = true;
  error.value = '';
  try {
    await api.deleteChallenge(props.id, false);
    await router.push('/challenges');
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除题目失败。';
  } finally {
    deleting.value = false;
  }
}

function statusClass(status: string) {
  return `status-${status}`;
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
}

function runKey(run: Run) {
  return String(run.id);
}

function isCancelling(run: Run) {
  return cancellingIds.value.has(runKey(run));
}

function replaceRun(nextRun: Run) {
  runs.value = runs.value.map((run) => (run.id === nextRun.id ? nextRun : run));
}

async function cancelRun(run: Run) {
  if (!canCancelRun(run) || isCancelling(run)) return;
  const key = runKey(run);
  cancellingIds.value = new Set(cancellingIds.value).add(key);
  runError.value = '';
  try {
    replaceRun(await api.cancelRun(run.id));
  } catch (err) {
    runError.value = err instanceof Error ? err.message : '停止运行失败。';
  } finally {
    const next = new Set(cancellingIds.value);
    next.delete(key);
    cancellingIds.value = next;
  }
}

onMounted(() => {
  load();
  loadModels();
  loadRuns();
  pollTimer = window.setInterval(() => {
    if (runs.value.some((run) => run.active || canCancelRun(run))) {
      loadRuns(true);
    }
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer);
});
</script>
