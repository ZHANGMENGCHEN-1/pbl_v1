import { createRouter, createWebHistory } from 'vue-router'
import { routes as astronomyRoutes } from './projects/astronomy/routes'
import { routes as libraryRoutes } from './projects/library/routes'
import { routes as teachingRoutes } from './projects/teaching-agent/routes'
import { routes as teachingCopyRoutes } from './projects/teaching-agent-copy/routes'
import { routes as activityRoutes } from './projects/learning-activities/routes'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./pages/home/ProjectHome.vue') },
    ...astronomyRoutes,
    ...libraryRoutes,
    ...teachingRoutes,
    ...teachingCopyRoutes,
    ...activityRoutes,
    { path: '/:pathMatch(.*)*', component: () => import('./pages/NotFound.vue') },
  ],
})
