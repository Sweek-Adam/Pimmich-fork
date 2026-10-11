import { createRouter, createWebHashHistory } from "vue-router";

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: () => import("./views/HomeView.vue") },
    { path: "/carte", component: () => import("./views/TripsView.vue") },
    { path: "/statistiques", component: () => import("./views/StatsView.vue") },
    { path: "/:rest(.*)*", redirect: "/" },
  ],
  scrollBehavior: () => ({ top: 0 }),
});
