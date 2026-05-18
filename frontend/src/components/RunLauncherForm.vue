<template>
  <form class="form-grid" @submit.prevent="submit">
    <label class="toggle-field">
      <input v-model="useDefaultAgents" type="checkbox" />
      <span>使用设置里的 Agent 编排</span>
    </label>

    <div v-if="useDefaultAgents" class="agent-default-note">
      将按设置页的 Agent 数量、模型池和 Skills 启动。
    </div>

    <div v-else class="field">
      <label :for="fieldId">模型</label>
      <select :id="fieldId" v-model="selectedModel">
        <option v-for="model in modelOptions" :key="model" :value="model">{{ model }}</option>
      </select>
    </div>

    <label class="toggle-field">
      <input v-model="noSubmit" type="checkbox" />
      <span>仅本地运行，不提交 flag</span>
    </label>

    <label class="toggle-field">
      <input v-model="generateWriteup" type="checkbox" />
      <span>解出后生成最终 writeup</span>
    </label>

    <div class="actions">
      <button class="btn primary" type="submit" :disabled="launching || !canLaunch">
        <Play :size="16" />
        {{ launching ? '启动中' : '开始运行' }}
      </button>
      <span v-if="displayMessage" class="muted">{{ displayMessage }}</span>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { Play } from 'lucide-vue-next';

const props = defineProps<{
  challengeId: string | number;
  launching?: boolean;
  message?: string;
  models?: string[];
  defaultModel?: string;
}>();

const emit = defineEmits<{
  launch: [payload: { challenge_id: number; model_specs?: string[]; no_submit: boolean; generate_writeup: boolean }];
}>();

const fieldId = `model-specs-${String(props.challengeId)}`;
const selectedModel = ref(props.defaultModel ?? 'openai/gpt-5.5');
const useDefaultAgents = ref(true);
const noSubmit = ref(true);
const generateWriteup = ref(true);
const validationMessage = ref('');

const modelOptions = computed(() => {
  const configured = props.models ?? [];
  return configured.includes(selectedModel.value) ? configured : [selectedModel.value, ...configured];
});

const modelSpecs = computed(() => (selectedModel.value.trim() ? [selectedModel.value.trim()] : []));

const numericChallengeId = computed(() => {
  const value = typeof props.challengeId === 'number' ? props.challengeId : Number(props.challengeId);
  return Number.isFinite(value) && Number.isInteger(value) ? value : null;
});

const canLaunch = computed(() => (useDefaultAgents.value || modelSpecs.value.length > 0) && numericChallengeId.value !== null);
const displayMessage = computed(() => validationMessage.value || props.message);

function submit() {
  validationMessage.value = '';
  if (numericChallengeId.value === null) {
    validationMessage.value = '题目 ID 必须是有效整数。';
    return;
  }
  if (!useDefaultAgents.value && modelSpecs.value.length === 0) return;
  const payload: { challenge_id: number; model_specs?: string[]; no_submit: boolean; generate_writeup: boolean } = {
    challenge_id: numericChallengeId.value,
    no_submit: noSubmit.value,
    generate_writeup: generateWriteup.value,
  };
  if (!useDefaultAgents.value) payload.model_specs = modelSpecs.value;
  emit('launch', payload);
}
</script>
