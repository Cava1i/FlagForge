<template>
  <div class="app-shell">
    <aside class="sidebar" aria-label="主导航">
      <RouterLink class="brand" to="/challenges">
        <span class="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span class="brand-copy">
          <strong>FlagForge</strong>
          <small>AI CTF War Room</small>
        </span>
      </RouterLink>

      <nav class="nav-links">
        <span class="nav-label">工作区</span>
        <RouterLink to="/challenges">
          <span class="nav-icon"><FolderKanban :size="18" /></span>
          <span>题目</span>
        </RouterLink>
        <RouterLink to="/runs">
          <span class="nav-icon"><Activity :size="18" /></span>
          <span>运行</span>
        </RouterLink>
        <RouterLink to="/settings">
          <span class="nav-icon"><Settings :size="18" /></span>
          <span>设置</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <span class="system-state"><i aria-hidden="true" /> 本地运行</span>
        <strong>REST API / SSE</strong>
        <small>SQLite 持久化</small>
      </div>
    </aside>

    <main class="workspace">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { Activity, FolderKanban, Settings } from 'lucide-vue-next';
</script>
