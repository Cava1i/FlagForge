<template>
  <form class="form-grid" @submit.prevent="submit">
    <div class="grid-2">
      <div class="field">
        <label for="challenge-name">题目名称</label>
        <input id="challenge-name" v-model="draft.name" autocomplete="off" />
      </div>
      <div class="field">
        <label for="challenge-category">分类</label>
        <input id="challenge-category" v-model="draft.category" autocomplete="off" />
      </div>
    </div>

    <div class="grid-2">
      <div class="field">
        <label for="challenge-value">分值</label>
        <input id="challenge-value" v-model.number="draft.value" min="0" type="number" />
      </div>
      <div class="field">
        <label for="challenge-tags">标签</label>
        <input id="challenge-tags" v-model="tagText" placeholder="crypto, warmup, remote" />
      </div>
    </div>

    <div class="field">
      <label for="challenge-connection">连接信息</label>
      <input id="challenge-connection" v-model="draft.connection_info" autocomplete="off" />
    </div>

    <div class="field">
      <label for="challenge-description">题目描述</label>
      <textarea id="challenge-description" v-model="draft.description" />
    </div>

    <div class="actions">
      <button class="btn primary" type="submit" :disabled="saving">
        <Save :size="16" />
        {{ saving ? '保存中' : '保存题目信息' }}
      </button>
      <span v-if="message" class="muted">{{ message }}</span>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import { Save } from 'lucide-vue-next';

import type { ChallengeMetadata, EditableChallengeMetadata } from '@/lib/api';

const props = defineProps<{
  metadata: Partial<ChallengeMetadata>;
  saving?: boolean;
  message?: string;
}>();

const emit = defineEmits<{
  save: [metadata: Partial<EditableChallengeMetadata>];
}>();

const draft = reactive<Partial<ChallengeMetadata>>({});

watch(
  () => props.metadata,
  (metadata) => {
    Object.assign(draft, {
      name: metadata.name ?? '',
      category: metadata.category ?? '',
      value: metadata.value ?? 0,
      description: metadata.description ?? '',
      connection_info: metadata.connection_info ?? '',
      tags: [...(metadata.tags ?? [])],
      hints: metadata.hints ?? [],
    });
  },
  { immediate: true },
);

const tagText = computed({
  get: () => (draft.tags ?? []).join(', '),
  set: (value: string) => {
    draft.tags = value
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
  },
});

function submit() {
  emit('save', {
    name: draft.name ?? '',
    category: draft.category ?? '',
    value: Number(draft.value ?? 0),
    description: draft.description ?? '',
    connection_info: draft.connection_info ?? '',
    tags: [...(draft.tags ?? [])],
    hints: [...(draft.hints ?? [])],
  });
}
</script>
