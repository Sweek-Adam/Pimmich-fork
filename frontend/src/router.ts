import { createRouter, createWebHashHistory } from "vue-router";

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: () => import("./views/HomeView.vue") },
    { path: "/carte", component: () => import("./views/TripsView.vue") },
    { path: "/statistiques", component: () => import("./views/StatsView.vue") },
    { path: "/a-valider", component: () => import("./views/PendingView.vue") },
    { path: "/bibliotheque", component: () => import("./views/LibraryView.vue") },
    { path: "/a-suivre", component: () => import("./views/QueueView.vue") },
    { path: "/messages", component: () => import("./views/MessagesView.vue") },
    { path: "/favoris", component: () => import("./views/LibraryView.vue"), props: { favorites: true } },
    { path: "/:rest(.*)*", redirect: "/" },
  ],
  scrollBehavior: () => ({ top: 0 }),
});
