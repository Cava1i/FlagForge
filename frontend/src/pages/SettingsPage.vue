<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">设置</h1>
        <p class="page-kicker">配置第三方中转站、模型密钥、Agent 编排、Writeup 提示词和 CTFd 凭据。</p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadAll">
        <RefreshCw :size="16" />
        {{ loading ? '刷新中' : '刷新' }}
      </button>
    </header>

    <p v-if="error" class="notice error">{{ error }}</p>
    <p v-if="message" class="notice">{{ message }}</p>

    <div class="metric-grid">
      <article class="metric-card">
        <span>模型配置</span>
        <strong>{{ configuredCount(modelFields) }}/{{ modelFields.length }}</strong>
        <small>中转站 / Key / Provider</small>
      </article>
      <article class="metric-card">
        <span>模型列表</span>
        <strong>{{ modelCatalog.model_count ?? modelOptions.length }}</strong>
        <small>{{ modelSourceLabel }}</small>
      </article>
      <article class="metric-card">
        <span>Agent 编排</span>
        <strong>{{ agentCount }}</strong>
        <small>{{ selectedModelList.length }} 个模型，{{ selectedSkillList.length }} 个 Skills</small>
      </article>
      <article class="metric-card">
        <span>配置文件</span>
        <strong class="metric-path">{{ config?.env_path ?? '.env' }}</strong>
        <small>本地单用户配置</small>
      </article>
    </div>

    <section class="panel">
      <div class="panel-header">
        <h2 class="panel-title">配置文件</h2>
      </div>
      <div class="panel-body">
        <code class="config-path">{{ config?.env_path ?? '.env' }}</code>
      </div>
    </section>

    <form class="settings-grid" @submit.prevent="save">
      <section class="panel panel-accent">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">第三方中转站 API 接口</h2>
            <span class="panel-kicker">OpenAI 兼容 /models</span>
          </div>
          <div class="actions">
            <span class="muted">{{ modelSourceLabel }}</span>
            <button class="btn" type="button" :disabled="testingModels" @click="testModelApi">
              <PlugZap :size="16" />
              {{ testingModels ? '测试中' : '测试接口' }}
            </button>
          </div>
        </div>
        <div class="panel-body form-grid">
          <div v-if="relayField" class="field">
            <label for="OPENAI_BASE_URL">{{ fieldLabel(relayField.key) }}</label>
            <input id="OPENAI_BASE_URL" v-model="draft.OPENAI_BASE_URL" autocomplete="off" placeholder="https://api.psydo.top" />
            <small class="muted">后端 solver 和模型列表接口都会使用这里的地址。</small>
          </div>

          <div class="config-detail-grid">
            <article>
              <span>当前 Base URL</span>
              <strong class="mono">{{ modelCatalog.base_url || draft.OPENAI_BASE_URL || '-' }}</strong>
            </article>
            <article>
              <span>接口状态</span>
              <strong>{{ modelCatalog.error ? '不可用' : '可用' }}</strong>
            </article>
            <article>
              <span>来源</span>
              <strong>{{ modelSourceLabel }}</strong>
            </article>
            <article>
              <span>默认模型</span>
              <strong class="mono">{{ (modelCatalog.default_models ?? []).join(', ') || 'openai/gpt-5.5' }}</strong>
            </article>
          </div>

          <div class="field">
            <label>后端模型列表请求</label>
            <div class="endpoint-list">
              <code v-for="url in modelCatalog.candidate_urls ?? []" :key="url">{{ url }}</code>
              <code v-if="!(modelCatalog.candidate_urls ?? []).length">{{ (draft.OPENAI_BASE_URL || 'https://api.psydo.top').replace(/\/$/, '') }}/models</code>
            </div>
          </div>

          <div v-if="modelApiTest" class="notice" :class="{ error: !modelApiTest.ok }">
            <strong>{{ modelApiTest.ok ? '中转站接口测试通过' : '中转站接口测试失败' }}</strong>
            <span class="model-test-detail">
              {{ modelApiTest.ok
                ? `命中 ${modelApiTest.checked_url}，返回 ${modelApiTest.model_count} 个模型${formatLatency(modelApiTest.latency_ms)}。`
                : modelApiTest.error }}
            </span>
            <span v-if="modelApiTest.ok && modelApiTest.sample_models.length" class="model-test-detail mono">
              {{ modelApiTest.sample_models.join(', ') }}
            </span>
          </div>

          <p v-if="modelCatalog.error" class="notice error">模型接口暂不可用：{{ modelCatalog.error }}</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">模型 API 密钥</h2>
          <span class="muted">{{ configuredCount(modelCredentialFields) }}/{{ modelCredentialFields.length }} 已配置</span>
        </div>
        <div class="panel-body form-grid">
          <div v-for="field in modelCredentialFields" :key="field.key" class="config-row">
            <div>
              <label :for="field.key">{{ fieldLabel(field.key) }}</label>
              <span class="mono">{{ field.key }}</span>
            </div>
            <div class="config-control">
              <div class="secret-input-row">
                <input
                  :id="field.key"
                  v-model="draft[field.key]"
                  :type="field.sensitive && !secretVisible[field.key] ? 'password' : 'text'"
                  :placeholder="fieldPlaceholder(field)"
                  autocomplete="off"
                />
                <button
                  v-if="field.sensitive"
                  class="btn icon-btn"
                  type="button"
                  :disabled="revealingSecrets[field.key]"
                  :title="secretVisible[field.key] ? '隐藏密钥' : '查看密钥'"
                  @click="toggleSecret(field)"
                >
                  <EyeOff v-if="secretVisible[field.key]" :size="16" />
                  <Eye v-else :size="16" />
                </button>
              </div>
              <label v-if="field.sensitive" class="inline-check">
                <input v-model="clearSecrets[field.key]" type="checkbox" />
                清空
              </label>
            </div>
            <span class="status-badge" :class="field.configured ? 'status-succeeded' : 'status-queued'">
              {{ field.configured ? '已配置' : '未配置' }}
            </span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Agent 编排</h2>
            <span class="panel-kicker">默认模型 gpt-5.5</span>
          </div>
          <span class="muted">{{ modelSourceLabel }}</span>
        </div>
        <div class="panel-body form-grid">
          <div class="grid-2">
            <div class="field">
              <label for="FLAGFORGE_AGENT_COUNT">后端同时运行的 Agent 数量</label>
              <input id="FLAGFORGE_AGENT_COUNT" v-model="draft.FLAGFORGE_AGENT_COUNT" type="number" min="1" max="12" />
            </div>
            <div class="field">
              <label>模型来源</label>
              <code class="config-path">{{ modelCatalog.base_url || draft.OPENAI_BASE_URL || 'https://api.openai.com/v1' }}</code>
            </div>
          </div>

          <div class="field">
            <label for="FLAGFORGE_AGENT_MODELS">Agent 模型池</label>
            <textarea
              id="FLAGFORGE_AGENT_MODELS"
              v-model="draft.FLAGFORGE_AGENT_MODELS"
              class="compact-textarea"
              placeholder="gpt-5.5 或 openai/gpt-5.5，每行一个"
            />
            <div class="model-chip-grid">
              <button
                v-for="model in modelOptions"
                :key="model"
                class="model-chip"
                :class="{ selected: modelSelected(model) }"
                type="button"
                @click="toggleModel(model)"
              >
                {{ displayModel(model) }}
              </button>
            </div>
          </div>

          <div class="field">
            <label for="FLAGFORGE_AGENT_SKILLS">启用 Skills</label>
            <textarea
              id="FLAGFORGE_AGENT_SKILLS"
              v-model="draft.FLAGFORGE_AGENT_SKILLS"
              class="compact-textarea"
              placeholder="ctf-web, ctf-misc"
            />
            <div class="skill-grid">
              <label v-for="skill in availableSkills" :key="skill.name" class="skill-option">
                <input :checked="skillSelected(skill.name)" type="checkbox" @change="toggleSkill(skill.name)" />
                <span>
                  <strong>{{ skill.name }}</strong>
                  <small>{{ skill.description || skill.path }}</small>
                </span>
              </label>
            </div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Writeup 生成提示词</h2>
            <span class="panel-kicker">默认中文</span>
          </div>
          <span class="muted">解出 flag 后发送给获胜 Agent</span>
        </div>
        <div class="panel-body form-grid">
          <div v-for="field in writeupFields" :key="field.key" class="field">
            <label :for="field.key">{{ fieldLabel(field.key) }}</label>
            <textarea
              :id="field.key"
              v-model="draft[field.key]"
              class="writeup-prompt-editor"
              placeholder="请输入生成 writeup 的提示词"
            />
            <small class="muted">这个提示词会在成功解出题目后发送给获胜 Agent，用于生成前端可查看和可下载的 Markdown。</small>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">CTFd</h2>
          <span class="muted">{{ configuredCount(ctfdFields) }}/{{ ctfdFields.length }} 已配置</span>
        </div>
        <div class="panel-body form-grid">
          <div v-for="field in ctfdFields" :key="field.key" class="config-row">
            <div>
              <label :for="field.key">{{ fieldLabel(field.key) }}</label>
              <span class="mono">{{ field.key }}</span>
            </div>
            <div class="config-control">
              <div class="secret-input-row">
                <input
                  :id="field.key"
                  v-model="draft[field.key]"
                  :type="field.sensitive && !secretVisible[field.key] ? 'password' : 'text'"
                  :placeholder="fieldPlaceholder(field)"
                  autocomplete="off"
                />
                <button
                  v-if="field.sensitive"
                  class="btn icon-btn"
                  type="button"
                  :disabled="revealingSecrets[field.key]"
                  :title="secretVisible[field.key] ? '隐藏密钥' : '查看密钥'"
                  @click="toggleSecret(field)"
                >
                  <EyeOff v-if="secretVisible[field.key]" :size="16" />
                  <Eye v-else :size="16" />
                </button>
              </div>
              <label v-if="field.sensitive" class="inline-check">
                <input v-model="clearSecrets[field.key]" type="checkbox" />
                清空
              </label>
            </div>
            <span class="status-badge" :class="field.configured ? 'status-succeeded' : 'status-queued'">
              {{ field.configured ? '已配置' : '未配置' }}
            </span>
          </div>
        </div>
      </section>

      <div class="actions">
        <button class="btn primary" type="submit" :disabled="saving || !config">
          <Save :size="16" />
          {{ saving ? '保存中' : '保存配置' }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { Eye, EyeOff, PlugZap, RefreshCw, Save } from 'lucide-vue-next';

import {
  api,
  type AvailableSkill,
  type ConfigFieldStatus,
  type ConfigStatus,
  type ModelApiTestResult,
  type ModelCatalog,
} from '@/lib/api';

const LABELS: Record<string, string> = {
  OPENAI_API_KEY: 'OpenAI API Key',
  OPENAI_BASE_URL: '第三方中转站 API 接口',
  ANTHROPIC_API_KEY: 'Anthropic API Key',
  ANTHROPIC_BASE_URL: 'Anthropic Base URL',
  ANTHROPIC_AUTH_TOKEN: 'Anthropic Auth Token',
  GEMINI_API_KEY: 'Gemini API Key',
  CTFD_URL: 'CTFd 地址',
  CTFD_TOKEN: 'CTFd Token',
  CTFD_USER: 'CTFd 用户名',
  CTFD_PASS: 'CTFd 密码',
  FLAGFORGE_AGENT_COUNT: 'Agent 数量',
  FLAGFORGE_AGENT_MODELS: 'Agent 模型池',
  FLAGFORGE_AGENT_SKILLS: 'Agent Skills',
  FLAGFORGE_WRITEUP_PROMPT: 'Writeup 生成提示词',
};

const config = ref<ConfigStatus | null>(null);
const modelCatalog = ref<ModelCatalog>({
  models: [],
  model_ids: [],
  default_models: ['openai/gpt-5.5'],
  source: 'fallback',
  model_count: 0,
});
const draft = reactive<Record<string, string>>({});
const clearSecrets = reactive<Record<string, boolean>>({});
const secretVisible = reactive<Record<string, boolean>>({});
const revealingSecrets = reactive<Record<string, boolean>>({});
const loading = ref(false);
const saving = ref(false);
const testingModels = ref(false);
const modelApiTest = ref<ModelApiTestResult | null>(null);
const error = ref('');
const message = ref('');

const fields = computed(() => Object.values(config.value?.fields ?? {}));
const modelFields = computed(() => fields.value.filter((field) => field.group === 'models'));
const relayField = computed(() => modelFields.value.find((field) => field.key === 'OPENAI_BASE_URL'));
const modelCredentialFields = computed(() => modelFields.value.filter((field) => field.key !== 'OPENAI_BASE_URL'));
const ctfdFields = computed(() => fields.value.filter((field) => field.group === 'ctfd'));
const writeupFields = computed(() => fields.value.filter((field) => field.group === 'writeup'));
const availableSkills = computed<AvailableSkill[]>(() => config.value?.available_skills ?? []);
const selectedModelList = computed(() => splitList(draft.FLAGFORGE_AGENT_MODELS || 'gpt-5.5'));
const selectedSkillList = computed(() => splitList(draft.FLAGFORGE_AGENT_SKILLS || ''));
const agentCount = computed(() => {
  const parsed = Number(draft.FLAGFORGE_AGENT_COUNT || config.value?.agent_defaults?.count || 1);
  return Number.isFinite(parsed) ? parsed : 1;
});
const modelOptions = computed(() => {
  const fromApi = modelCatalog.value.models ?? [];
  const selected = selectedModelList.value.map(normalizeModelSpec);
  return Array.from(new Set([...selected, ...fromApi]));
});
const modelSourceLabel = computed(() => (modelCatalog.value.source === 'api' ? '来自 API 中转站' : '使用本地兜底'));

function fieldLabel(key: string) {
  return LABELS[key] ?? key;
}

function fieldPlaceholder(field: ConfigFieldStatus) {
  if (field.sensitive) return field.configured ? '点击眼睛查看，留空保持不变' : '输入密钥';
  return fieldLabel(field.key);
}

function configuredCount(items: ConfigFieldStatus[]) {
  return items.filter((field) => field.configured).length;
}

function formatLatency(value?: number | null) {
  return typeof value === 'number' ? `，耗时 ${value}ms` : '';
}

function hydrateDraft(nextConfig: ConfigStatus) {
  for (const field of Object.values(nextConfig.fields)) {
    draft[field.key] = field.sensitive ? '' : field.value ?? '';
    clearSecrets[field.key] = false;
    secretVisible[field.key] = false;
    revealingSecrets[field.key] = false;
  }
  draft.FLAGFORGE_AGENT_COUNT ||= String(nextConfig.agent_defaults?.count ?? 1);
  draft.FLAGFORGE_AGENT_MODELS ||= (nextConfig.agent_defaults?.models ?? ['gpt-5.5']).join('\n');
  draft.FLAGFORGE_AGENT_SKILLS ||= (nextConfig.agent_defaults?.skills ?? []).join('\n');
}

async function loadModels() {
  try {
    modelCatalog.value = await api.listModels();
  } catch (err) {
    modelCatalog.value = {
      models: [],
      model_ids: [],
      default_models: ['openai/gpt-5.5'],
      source: 'fallback',
      model_count: 0,
      error: err instanceof Error ? err.message : '模型列表加载失败',
    };
  }
}

async function testModelApi() {
  testingModels.value = true;
  error.value = '';
  message.value = '';
  modelApiTest.value = null;
  try {
    modelApiTest.value = await api.testModels({
      base_url: draft.OPENAI_BASE_URL,
      api_key: draft.OPENAI_API_KEY,
    });
    if (modelApiTest.value.ok) {
      await loadModels();
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '测试中转站接口失败。';
  } finally {
    testingModels.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = '';
  message.value = '';
  try {
    const nextConfig = await api.getConfig();
    config.value = nextConfig;
    hydrateDraft(nextConfig);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载配置失败。';
  } finally {
    loading.value = false;
  }
}

async function loadAll() {
  await load();
  await loadModels();
}

async function toggleSecret(field: ConfigFieldStatus) {
  if (!field.sensitive) return;
  if (secretVisible[field.key]) {
    secretVisible[field.key] = false;
    return;
  }

  error.value = '';
  try {
    if (!draft[field.key] && field.configured) {
      revealingSecrets[field.key] = true;
      const secret = await api.revealSecret(field.key);
      draft[field.key] = secret.value;
    }
    secretVisible[field.key] = true;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取密钥失败。';
  } finally {
    revealingSecrets[field.key] = false;
  }
}

async function save() {
  if (!config.value) return;
  saving.value = true;
  error.value = '';
  message.value = '';
  const values: Record<string, string> = {};

  for (const field of Object.values(config.value.fields)) {
    if (field.sensitive) {
      if (clearSecrets[field.key]) {
        values[field.key] = '';
      } else if (draft[field.key]?.trim()) {
        values[field.key] = draft[field.key].trim();
      }
    } else {
      values[field.key] = draft[field.key] ?? '';
    }
  }

  try {
    const nextConfig = await api.updateConfig(values);
    config.value = nextConfig;
    hydrateDraft(nextConfig);
    await loadModels();
    message.value = '配置已保存到本地 .env。';
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存配置失败。';
  } finally {
    saving.value = false;
  }
}

function splitList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeModelSpec(model: string) {
  return model.includes('/') ? model : `openai/${model}`;
}

function displayModel(model: string) {
  return model.startsWith('openai/') ? model.slice('openai/'.length) : model;
}

function modelSelected(model: string) {
  const normalized = normalizeModelSpec(model);
  return selectedModelList.value.map(normalizeModelSpec).includes(normalized);
}

function toggleModel(model: string) {
  const normalized = normalizeModelSpec(model);
  const current = selectedModelList.value.map(normalizeModelSpec);
  const next = current.includes(normalized)
    ? current.filter((item) => item !== normalized)
    : [...current, normalized];
  draft.FLAGFORGE_AGENT_MODELS = next.join('\n');
}

function skillSelected(skill: string) {
  return selectedSkillList.value.includes(skill);
}

function toggleSkill(skill: string) {
  const current = selectedSkillList.value;
  const next = current.includes(skill) ? current.filter((item) => item !== skill) : [...current, skill];
  draft.FLAGFORGE_AGENT_SKILLS = next.join('\n');
}

onMounted(() => {
  loadAll();
});
</script>
