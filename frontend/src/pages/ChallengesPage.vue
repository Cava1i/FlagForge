<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">题目</h1>
        <p class="page-kicker">手动创建、导入本地题目，并启动单题运行。</p>
      </div>
      <button class="btn" type="button" @click="load">
        <RefreshCw :size="16" />
        刷新
      </button>
    </header>

    <div class="metric-grid">
      <article class="metric-card">
        <span>题目总数</span>
        <strong>{{ challenges.length }}</strong>
        <small>本地索引</small>
      </article>
      <article class="metric-card">
        <span>题目分类</span>
        <strong>{{ categoryCount }}</strong>
        <small>按 metadata 聚合</small>
      </article>
      <article class="metric-card">
        <span>远程服务</span>
        <strong>{{ remoteCount }}</strong>
        <small>含连接信息</small>
      </article>
      <article class="metric-card">
        <span>总分值</span>
        <strong>{{ totalPoints }}</strong>
        <small>已录入题目</small>
      </article>
    </div>

    <div class="split-grid split-grid-wide">
    <section class="panel panel-accent">
      <div class="panel-header">
        <h2 class="panel-title">手动创建题目</h2>
        <span class="panel-kicker">metadata.yml + distfiles</span>
      </div>
      <div class="panel-body">
        <form class="form-grid" @submit.prevent="createManual">
          <div class="grid-2">
            <div class="field">
              <label for="manual-slug">目录名 slug</label>
              <input id="manual-slug" v-model="manualSlug" autocomplete="off" placeholder="manual-web-warmup" />
            </div>
            <div class="field">
              <label for="manual-name">题目名称</label>
              <input id="manual-name" v-model="manualDraft.name" autocomplete="off" required />
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label for="manual-category">分类</label>
              <input id="manual-category" v-model="manualDraft.category" autocomplete="off" />
            </div>
            <div class="field">
              <label for="manual-value">分值</label>
              <input id="manual-value" v-model.number="manualDraft.value" min="0" type="number" />
            </div>
          </div>

          <div class="grid-2">
            <div class="field">
              <label for="manual-tags">标签</label>
              <input id="manual-tags" v-model="manualTagText" placeholder="web, warmup, upload" />
            </div>
            <div class="field">
              <label for="manual-connection">连接信息</label>
              <input id="manual-connection" v-model="manualDraft.connection_info" autocomplete="off" />
            </div>
          </div>

          <div class="field">
            <label for="manual-description">题目描述</label>
            <textarea id="manual-description" v-model="manualDraft.description" />
          </div>

          <div class="field">
            <label for="manual-files">附件文件 distfiles</label>
            <div class="file-picker">
              <input
                id="manual-files"
                ref="manualFileInput"
                class="file-input"
                type="file"
                multiple
                @change="selectManualFiles"
              />
              <label class="btn" for="manual-files">
                <Upload :size="16" />
                选择附件
              </label>
              <span class="muted">{{ manualFiles.length ? `${manualFiles.length} 个文件已选择` : '未选择附件' }}</span>
            </div>
          </div>

          <div v-if="manualFiles.length" class="upload-list">
            <div v-for="(item, index) in manualFiles" :key="`${item.file.name}-${item.file.lastModified}-${index}`" class="upload-row">
              <div>
                <strong>{{ item.file.name }}</strong>
                <span>{{ formatBytes(item.file.size) }}</span>
              </div>
              <div class="field compact-field">
                <label :for="`manual-file-name-${index}`">保存文件名</label>
                <input :id="`manual-file-name-${index}`" v-model="item.name" autocomplete="off" />
              </div>
              <button class="btn icon-btn" type="button" :aria-label="`移除 ${item.file.name}`" @click="removeManualFile(index)">
                <X :size="16" />
              </button>
            </div>
          </div>

          <div class="actions">
            <button class="btn primary" type="submit" :disabled="manualCreating || !String(manualDraft.name ?? '').trim()">
              <Upload :size="16" />
              {{ manualCreating ? '创建中' : '创建题目' }}
            </button>
            <span v-if="manualMessage" class="muted">{{ manualMessage }}</span>
          </div>
        </form>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">从本地目录导入</h2>
        <span class="panel-kicker">复用现有目录</span>
      </div>
      <div class="panel-body">
        <form class="form-grid" @submit.prevent="importPath">
          <div class="field">
            <label for="challenge-path">题目目录</label>
            <input
              id="challenge-path"
              v-model="pathInput"
              autocomplete="off"
              placeholder="/home/ctf-agent/challenges/test_your_nc"
            />
          </div>
          <div class="actions">
            <button class="btn primary" type="submit" :disabled="importing || !pathInput.trim()">
              <FolderInput :size="16" />
              {{ importing ? '导入中' : '导入题目' }}
            </button>
            <span v-if="importMessage" class="muted">{{ importMessage }}</span>
          </div>
        </form>
      </div>
    </section>
    </div>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">本地题目列表</h2>
        <span class="muted">共 {{ challenges.length }} 个</span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>分类</th>
              <th>分值</th>
              <th>连接信息</th>
              <th>路径</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="6" class="muted">正在加载题目...</td>
            </tr>
            <tr v-else-if="challenges.length === 0">
              <td colspan="6" class="muted">还没有导入题目。</td>
            </tr>
            <tr v-for="challenge in challenges" v-else :key="challenge.id">
              <td>
                <RouterLink class="link-row" :to="`/challenges/${challenge.id}`">
                  {{ meta(challenge).name || `题目 ${challenge.id}` }}
                </RouterLink>
              </td>
              <td>{{ meta(challenge).category || '-' }}</td>
              <td>{{ meta(challenge).value ?? '-' }}</td>
              <td class="mono">{{ meta(challenge).connection_info || '-' }}</td>
              <td class="mono">{{ challenge.path ?? challenge.challenge_dir ?? '-' }}</td>
              <td>
                <div class="table-actions">
                  <button
                    class="btn compact danger"
                    type="button"
                    :disabled="isDeleting(challenge)"
                    @click="deleteChallenge(challenge)"
                  >
                    <Trash2 :size="15" />
                    {{ isDeleting(challenge) ? '删除中' : '删除' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="error" class="notice error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { FolderInput, RefreshCw, Trash2, Upload, X } from 'lucide-vue-next';

import { api, challengeMeta, type Challenge, type EditableChallengeMetadata, type ManualChallengeFile } from '@/lib/api';

const challenges = ref<Challenge[]>([]);
const loading = ref(false);
const importing = ref(false);
const manualCreating = ref(false);
const pathInput = ref('');
const error = ref('');
const importMessage = ref('');
const manualMessage = ref('');
const manualSlug = ref('');
const manualFileInput = ref<HTMLInputElement | null>(null);
const manualFiles = ref<ManualChallengeFile[]>([]);
const deletingIds = ref<Set<string>>(new Set());
const manualDraft = reactive<Partial<EditableChallengeMetadata>>({
  name: '',
  category: '',
  value: 0,
  description: '',
  connection_info: '',
  tags: [],
  hints: [],
});

const totalPoints = computed(() =>
  challenges.value.reduce((total, challenge) => total + Number(meta(challenge).value ?? 0), 0),
);
const categoryCount = computed(
  () => new Set(challenges.value.map((challenge) => meta(challenge).category).filter(Boolean)).size,
);
const remoteCount = computed(
  () => challenges.value.filter((challenge) => Boolean(meta(challenge).connection_info)).length,
);

const manualTagText = computed({
  get: () => (manualDraft.tags ?? []).join(', '),
  set: (value: string) => {
    manualDraft.tags = value
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  },
});

function meta(challenge: Challenge) {
  return challengeMeta(challenge);
}

function challengeKey(challenge: Challenge) {
  return String(challenge.id);
}

function isDeleting(challenge: Challenge) {
  return deletingIds.value.has(challengeKey(challenge));
}

async function load() {
  loading.value = true;
  error.value = '';
  try {
    challenges.value = await api.listChallenges();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载题目失败。';
  } finally {
    loading.value = false;
  }
}

async function importPath() {
  if (!pathInput.value.trim()) return;
  importing.value = true;
  error.value = '';
  importMessage.value = '';
  try {
    const challenge = await api.importChallenge(pathInput.value.trim());
    importMessage.value = '题目已导入。';
    pathInput.value = '';
    challenges.value = [challenge, ...challenges.value.filter((item) => item.id !== challenge.id)];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '导入题目失败。';
  } finally {
    importing.value = false;
  }
}

function selectManualFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  manualFiles.value = files.map((file) => ({ file, name: file.name }));
}

function removeManualFile(index: number) {
  manualFiles.value = manualFiles.value.filter((_item, itemIndex) => itemIndex !== index);
}

function resetManualForm() {
  manualSlug.value = '';
  manualFiles.value = [];
  Object.assign(manualDraft, {
    name: '',
    category: '',
    value: 0,
    description: '',
    connection_info: '',
    tags: [],
    hints: [],
  });
  if (manualFileInput.value) {
    manualFileInput.value.value = '';
  }
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

async function createManual() {
  manualCreating.value = true;
  manualMessage.value = '';
  error.value = '';
  try {
    const challenge = await api.createManualChallenge({
      slug: manualSlug.value,
      metadata: {
        name: manualDraft.name ?? '',
        category: manualDraft.category ?? '',
        value: Number(manualDraft.value ?? 0),
        description: manualDraft.description ?? '',
        connection_info: manualDraft.connection_info ?? '',
        tags: [...(manualDraft.tags ?? [])],
        hints: [...(manualDraft.hints ?? [])],
      },
      files: manualFiles.value,
    });
    manualMessage.value = '题目已创建。';
    resetManualForm();
    challenges.value = [challenge, ...challenges.value.filter((item) => item.id !== challenge.id)];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '创建题目失败。';
  } finally {
    manualCreating.value = false;
  }
}

async function deleteChallenge(challenge: Challenge) {
  const name = meta(challenge).name || `题目 ${challenge.id}`;
  if (!window.confirm(`确认从 FlagForge 删除「${name}」？本地文件默认保留。`)) return;
  const key = challengeKey(challenge);
  deletingIds.value = new Set(deletingIds.value).add(key);
  error.value = '';
  try {
    await api.deleteChallenge(challenge.id, false);
    challenges.value = challenges.value.filter((item) => item.id !== challenge.id);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除题目失败。';
  } finally {
    const next = new Set(deletingIds.value);
    next.delete(key);
    deletingIds.value = next;
  }
}

onMounted(load);
</script>
