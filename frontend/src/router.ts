import { createRouter, createWebHistory } from 'vue-router'
import { routes as astronomyRoutes } from './projects/astronomy/routes'
import { routes as libraryRoutes } from './projects/library/routes'
import { routes as teachingRoutes } from './projects/teaching-agent/routes'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./pages/home/ProjectHome.vue') },
    ...astronomyRoutes,
    ...libraryRoutes,
    ...teachingRoutes,
    { path: '/:pathMatch(.*)*', component: () => import('./pages/NotFound.vue') },
  ],
})
