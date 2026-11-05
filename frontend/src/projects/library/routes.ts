import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/projects/library-recommendation', name: 'library', component: () => import('./Workspace.vue') },
]
