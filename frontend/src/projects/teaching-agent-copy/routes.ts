import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/projects/meaning-making', name: 'meaning-making', component: () => import('./Workspace.vue') },
]
