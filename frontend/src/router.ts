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
    { path: "/playlists", component: () => import("./views/PlaylistsView.vue") },
    { path: "/affichage", component: () => import("./views/DisplayView.vue") },
    { path: "/horloge-meteo", component: () => import("./views/ClockView.vue") },
    { path: "/infos-photos", component: () => import("./views/PhotoInfoView.vue") },
    { path: "/journaux", component: () => import("./views/LogsView.vue") },
    { path: "/dispositions", component: () => import("./views/LayoutsView.vue") },
    { path: "/favoris", component: () => import("./views/LibraryView.vue"), props: { favorites: true } },
    { path: "/:rest(.*)*", redirect: "/" },
  ],
  scrollBehavior: () => ({ top: 0 }),
});
