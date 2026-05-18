<template>
  <div class="markdown-view" :class="{ compact }">
    <p v-if="!content.trim()" class="muted">{{ emptyText }}</p>
    <template v-for="(block, index) in blocks" :key="index">
      <component
        :is="`h${block.level}`"
        v-if="block.type === 'heading'"
        class="md-heading"
        v-html="block.html"
      />
      <p v-else-if="block.type === 'paragraph'" class="md-paragraph" v-html="block.html" />
      <blockquote v-else-if="block.type === 'quote'" class="md-quote" v-html="block.html" />
      <ul v-else-if="block.type === 'list'" class="md-list">
        <li v-for="(item, itemIndex) in block.items" :key="itemIndex" v-html="item" />
      </ul>
      <div v-else-if="block.type === 'code'" class="md-code">
        <div class="md-code-head">
          <span>{{ block.language || 'text' }}</span>
          <button class="copy-code-btn" type="button" @click="copyCode(block.code, index)">
            <Check v-if="copiedIndex === index" :size="14" />
            <Copy v-else :size="14" />
            {{ copiedIndex === index ? '已复制' : '复制' }}
          </button>
        </div>
        <pre><code>{{ block.code }}</code></pre>
      </div>
      <hr v-else-if="block.type === 'rule'" class="md-rule" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { Check, Copy } from 'lucide-vue-next';

type MarkdownBlock =
  | { type: 'heading'; level: number; html: string }
  | { type: 'paragraph'; html: string }
  | { type: 'quote'; html: string }
  | { type: 'list'; items: string[] }
  | { type: 'code'; language: string; code: string }
  | { type: 'rule' };

const props = withDefaults(
  defineProps<{
    content?: string;
    emptyText?: string;
    compact?: boolean;
  }>(),
  {
    content: '',
    emptyText: '暂无内容。',
    compact: false,
  },
);

const copiedIndex = ref<number | null>(null);

const content = computed(() => props.content ?? '');
const blocks = computed(() => parseMarkdown(content.value));

async function copyCode(code: string, index: number) {
  try {
    await navigator.clipboard.writeText(code);
    copiedIndex.value = index;
    window.setTimeout(() => {
      if (copiedIndex.value === index) copiedIndex.value = null;
    }, 1200);
  } catch {
    copiedIndex.value = null;
  }
}

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const result: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let index = 0;

  function flushParagraph() {
    if (!paragraph.length) return;
    result.push({ type: 'paragraph', html: renderInline(paragraph.join(' ')) });
    paragraph = [];
  }

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    const fence = trimmed.match(/^```([A-Za-z0-9_+.-]*)\s*$/);
    if (fence) {
      flushParagraph();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        code.push(lines[index]);
        index += 1;
      }
      result.push({ type: 'code', language: fence[1] || '', code: code.join('\n') });
      index += 1;
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      index += 1;
      continue;
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      result.push({
        type: 'heading',
        level: Math.min(heading[1].length + 1, 5),
        html: renderInline(heading[2]),
      });
      index += 1;
      continue;
    }

    if (/^---+$/.test(trimmed)) {
      flushParagraph();
      result.push({ type: 'rule' });
      index += 1;
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(renderInline(lines[index].trim().replace(/^[-*]\s+/, '')));
        index += 1;
      }
      result.push({ type: 'list', items });
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      flushParagraph();
      const quotes: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quotes.push(lines[index].trim().replace(/^>\s?/, ''));
        index += 1;
      }
      result.push({ type: 'quote', html: renderInline(quotes.join(' ')) });
      continue;
    }

    paragraph.push(trimmed);
    index += 1;
  }

  flushParagraph();
  return result;
}

function renderInline(value: string): string {
  const codeParts: string[] = [];
  let html = escapeHtml(value).replace(/`([^`]+)`/g, (_, code: string) => {
    codeParts.push(`<code>${code}</code>`);
    return `@@CODE${codeParts.length - 1}@@`;
  });

  html = html
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');

  return html.replace(/@@CODE(\d+)@@/g, (_, rawIndex: string) => codeParts[Number(rawIndex)] ?? '');
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
</script>
