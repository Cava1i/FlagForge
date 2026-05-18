<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">运行</h1>
        <p class="page-kicker">查看解题历史、运行状态和结果摘要。</p>
      </div>
      <button class="btn" type="button" @click="load()">
        <RefreshCw :size="16" />
        刷新
      </button>
    </header>

    <p v-if="error" class="notice error">{{ error }}</p>

    <div class="metric-grid">
      <article class="metric-card">
        <span>运行总数</span>
        <strong>{{ runs.length }}</strong>
        <small>历史记录</small>
      </article>
      <article class="metric-card">
        <span>运行中</span>
        <strong>{{ runningCount }}</strong>
        <small>实时任务</small>
      </article>
      <article class="metric-card">
        <span>成功</span>
        <strong>{{ succeededCount }}</strong>
        <small>找到 flag</small>
      </article>
      <article class="metric-card">
        <span>失败</span>
        <strong>{{ failedCount }}</strong>
        <small>需复盘</small>
      </article>
    </div>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">运行历史</h2>
        <span class="muted">共 {{ runs.length }} 条</span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>运行</th>
              <th>状态</th>
              <th>题目</th>
              <th>模型</th>
              <th>结果</th>
              <th>开始时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="muted">正在加载运行记录...</td>
            </tr>
            <tr v-else-if="runs.length === 0">
              <td colspan="7" class="muted">还没有运行记录。</td>
            </tr>
            <tr v-for="run in runs" v-else :key="run.id">
              <td>
                <RouterLink class="link-row mono" :to="`/runs/${run.id}`">#{{ run.id }}</RouterLink>
              </td>
              <td><span class="status-badge" :class="statusClass(run.status)">{{ runStatusLabel(run.status) }}</span></td>
              <td>{{ run.challenge_name ?? run.challenge_id ?? '-' }}</td>
              <td class="mono">{{ (run.model_specs ?? []).join(', ') || '-' }}</td>
              <td><span class="summary-cell">{{ runSummary(run) }}</span></td>
              <td class="date-cell">{{ formatDate(run.started_at ?? run.created_at) }}</td>
              <td class="action-cell">
                <div class="table-actions">
                  <RouterLink class="btn compact" :to="`/runs/${run.id}`">
                    <ScrollText :size="15" />
                    日志
                  </RouterLink>
                  <button
                    class="btn compact danger"
                    type="button"
                    :disabled="!canCancelRun(run) || isCancelling(run)"
                    @click="cancel(run)"
                  >
                    <Square :size="15" />
                    {{ isCancelling(run) ? '停止中' : '停止' }}
                  </button>
                  <button
                    class="btn compact danger"
                    type="button"
                    :disabled="!isRunTerminal(run) || isDeleting(run)"
                    @click="deleteRun(run)"
                  >
                    <Trash2 :size="15" />
                    {{ isDeleting(run) ? '删除中' : '删除' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { RefreshCw, ScrollText, Square, Trash2 } from 'lucide-vue-next';

import { api, canCancelRun, isRunTerminal, runStatusLabel, runSummary, type Run } from '@/lib/api';

const runs = ref<Run[]>([]);
const loading = ref(false);
const error = ref('');
const cancellingIds = ref<Set<string>>(new Set());
const deletingIds = ref<Set<string>>(new Set());
let pollTimer: number | undefined;

const runningCount = computed(() => runs.value.filter((run) => run.status === 'running').length);
const succeededCount = computed(() => runs.value.filter((run) => run.status === 'succeeded').length);
const failedCount = computed(() => runs.value.filter((run) => run.status === 'failed').length);

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

function isDeleting(run: Run) {
  return deletingIds.value.has(runKey(run));
}

function replaceRun(next: Run) {
  runs.value = runs.value.map((run) => (run.id === next.id ? next : run));
}

async function load(silent = false) {
  if (!silent) loading.value = true;
  error.value = '';
  try {
    runs.value = await api.listRuns();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载运行记录失败。';
  } finally {
    if (!silent) loading.value = false;
  }
}

async function cancel(run: Run) {
  if (!canCancelRun(run) || isCancelling(run)) return;
  const key = runKey(run);
  cancellingIds.value = new Set(cancellingIds.value).add(key);
  error.value = '';
  try {
    replaceRun(await api.cancelRun(run.id));
  } catch (err) {
    error.value = err instanceof Error ? err.message : '停止运行失败。';
  } finally {
    const next = new Set(cancellingIds.value);
    next.delete(key);
    cancellingIds.value = next;
  }
}

async function deleteRun(run: Run) {
  if (!isRunTerminal(run) || isDeleting(run)) return;
  if (!window.confirm(`确认删除运行 #${run.id} 的历史记录和关联日志？`)) return;
  const key = runKey(run);
  deletingIds.value = new Set(deletingIds.value).add(key);
  error.value = '';
  try {
    await api.deleteRun(run.id);
    runs.value = runs.value.filter((item) => item.id !== run.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除运行记录失败。';
  } finally {
    const next = new Set(deletingIds.value);
    next.delete(key);
    deletingIds.value = next;
  }
}

onMounted(() => {
  load();
  pollTimer = window.setInterval(() => {
    if (runs.value.some((run) => run.active || canCancelRun(run))) {
      load(true);
    }
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer);
});
</script>
