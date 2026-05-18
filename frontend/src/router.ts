import { createRouter, createWebHistory } from 'vue-router';

import ChallengeDetailPage from './pages/ChallengeDetailPage.vue';
import ChallengesPage from './pages/ChallengesPage.vue';
import RunDetailPage from './pages/RunDetailPage.vue';
import RunsPage from './pages/RunsPage.vue';
import SettingsPage from './pages/SettingsPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/challenges' },
    { path: '/challenges', name: 'challenges', component: ChallengesPage },
    { path: '/challenges/:id', name: 'challenge-detail', component: ChallengeDetailPage, props: true },
    { path: '/runs', name: 'runs', component: RunsPage },
    { path: '/runs/:id', name: 'run-detail', component: RunDetailPage, props: true },
    { path: '/settings', name: 'settings', component: SettingsPage },
  ],
});

export default router;
