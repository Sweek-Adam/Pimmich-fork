<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface Station { url: string; name: string; genre?: string; country?: string }
interface Podcast { feed: string; name: string }
const stations = ref<Station[]>([]);
const favorites = ref<Station[]>([]);
const podcasts = ref<Podcast[]>([]);
const playing = ref<{ name: string } | null>(null);
const query = ref("");
const results = ref<Station[] | null>(null);
const feed = ref("");
let timer: number | undefined;

async function load() {
  const d = await get<{ stations: Station[]; favorites: Station[]; podcasts: Podcast[]; playing: { name: string } | null }>("/api/radio");
  stations.value = d.stations; favorites.value = d.favorites; podcasts.value = d.podcasts; playing.value = d.playing;
}
const isFav = (s: Station) => favorites.value.some((f) => f.url === s.url);
async function play(s: Station) { await run(() => post("/api/radio/play", { url: s.url, name: s.name })); window.setTimeout(load, 800); }
async function toggleFav(s: Station) {
  const d = await run(() => post<{ favorites: Station[]; message?: string }>("/api/radio/favorites", { url: s.url, name: s.name, remove: isFav(s) }));
  if (d) favorites.value = d.favorites;
}
async function stop() { await run(() => post("/api/radio/stop")); load(); }
function search() {
  window.clearTimeout(timer);
  timer = window.setTimeout(async () => {
    if (query.value.trim().length < 2) { results.value = null; return; }
    try { results.value = (await get<{ stations: Station[] }>(`/api/radio/search?q=${encodeURIComponent(query.value.trim())}`)).stations; }
    catch (e) { notify((e as Error).message, true); }
  }, 400);
}
async function playPodcast(p: Podcast) { notify("…"); await run(() => post("/api/podcast/play", { feed: p.feed })); window.setTimeout(load, 800); }
async function removePodcast(p: Podcast) { await run(() => post("/api/podcasts", { feed: p.feed, remove: true })); load(); }
async function addPodcast() { const done = await run(() => post("/api/podcasts", { feed: feed.value })); if (done) { feed.value = ""; load(); } }

onMounted(load);
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fas fa-broadcast-tower"></i>{{ t("Radios et podcasts") }}</h2></div>
    <div v-if="playing" class="now"><span><i class="fas fa-volume-up"></i> <strong>{{ playing.name }}</strong></span>
      <button class="btn small" type="button" @click="stop"><i class="fas fa-stop"></i>{{ t("Arrêter") }}</button></div>
    <template v-for="group in [{ title: t('Mes radios'), items: favorites }, { title: t('Radios'), items: stations }, { title: t('Trouver une radio'), items: results }]" :key="group.title">
      <h3 v-if="(group.items && group.items.length) || group.title === t('Trouver une radio')">{{ group.title }}</h3>
      <input v-if="group.title === t('Trouver une radio')" v-model="query" type="search" class="search" :placeholder="t('Nom de la radio (ex : RTL, Chérie FM, BBC...)')" @input="search">
      <p v-if="group.title === t('Trouver une radio') && results && !results.length" class="small muted">{{ t("Aucune radio trouvée.") }}</p>
      <div v-if="group.items && group.items.length" class="tiles">
        <div v-for="s in group.items" :key="s.url" class="tile">
          <button type="button" class="play" @click="play(s)"><i class="fas fa-play-circle"></i>
            <span><strong>{{ s.name }}</strong><small>{{ [s.genre, s.country].filter(Boolean).join(" · ") }}</small></span></button>
          <button type="button" class="star" :class="{ on: isFav(s) }" :title="isFav(s) ? t('Retirer de mes radios') : t('Ajouter à mes radios')" @click="toggleFav(s)">
            <i :class="isFav(s) ? 'fas fa-star' : 'far fa-star'"></i></button>
        </div>
      </div>
    </template>
    <h3>{{ t("Podcasts") }}</h3>
    <div class="tiles">
      <div v-for="p in podcasts" :key="p.feed" class="tile">
        <button type="button" class="play" :title="t('Écouter le dernier épisode')" @click="playPodcast(p)"><i class="fas fa-podcast"></i><span><strong>{{ p.name }}</strong></span></button>
        <button type="button" class="star" :title="t('Retirer')" @click="removePodcast(p)"><i class="fas fa-times"></i></button>
      </div>
    </div>
    <form class="row add" @submit.prevent="addPodcast">
      <input v-model="feed" type="url" class="spacer search" :placeholder="t('Adresse du flux RSS du podcast')">
      <button class="btn" type="submit"><i class="fas fa-plus"></i>{{ t("Ajouter") }}</button>
    </form>
  </section>
</template>

<style scoped>
.now { display: flex; align-items: center; gap: .8rem; justify-content: space-between; padding: .6rem .8rem; border-radius: 12px; background: var(--accent-soft); margin-bottom: .6rem; }
.now i { color: var(--accent); }
h3 { font-size: 1rem; margin: 1rem 0 .5rem; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .5rem; }
.tile { display: flex; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.play { flex: 1; display: flex; gap: .6rem; align-items: center; text-align: left; border: 0; background: none; color: var(--text); font: inherit; padding: .55rem .7rem; cursor: pointer; min-width: 0; }
.play:hover { background: var(--surface-2); }
.play i { color: var(--accent); font-size: 1.3rem; }
.play span { display: grid; min-width: 0; }
.play strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.play small { color: var(--muted); font-size: .75rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.star { border: 0; border-left: 1px solid var(--border); background: none; color: var(--muted); width: 2.6rem; cursor: pointer; }
.star.on { color: #e0a100; }
.search { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; width: 100%; margin-bottom: .5rem; min-width: 0; }
.add { margin-top: .7rem; }
.add .search { margin: 0; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
</style>
