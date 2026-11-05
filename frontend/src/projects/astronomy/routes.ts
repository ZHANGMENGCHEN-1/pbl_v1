import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/projects/astronomy-lab', name: 'astronomy', component: () => import('./Workspace.vue') },
]
