import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/projects/teaching-agent', name: 'teaching-agent', component: () => import('./Workspace.vue') },
]
