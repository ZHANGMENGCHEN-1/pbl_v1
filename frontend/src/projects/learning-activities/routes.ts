import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/projects/learning-activities', name: 'learning-activities', component: () => import('./Workspace.vue') },
]
