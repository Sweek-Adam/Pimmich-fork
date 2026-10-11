<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface SpotifyState {
  linked: boolean; pending: boolean; url?: string; code?: string; account?: string; redirect_uri: string; client_id: string;
  connected: boolean; links: Record<string, string>; ambiances: { key: string; label: string }[]; photo_playlists: { id: string; name: string }[];
}
interface Item { uri: string; name: string; artists?: string; thumb?: string }
interface Player {
  success: boolean; active: boolean; playing: boolean; device: string; on_frame: boolean; shuffle: boolean; repeat: string; volume: number | null;
  progress_ms: number; track: { name: string; artists: string; album: string; image: string; duration_ms: number }; queue: Item[];
}
interface Playlist { uri: string; name: string; image?: string; tracks: number }

const state = ref<SpotifyState | null>(null);
const player = ref<Player | null>(null);
const playlists = ref<Playlist[]>([]);
const clientId = ref("");
const showSetup = ref(false);
const filter = ref("");
const query = ref("");
const results = ref<Record<string, Item[]> | null>(null);
const position = ref(0);
const seeking = ref(false);
let tick = Date.now();
let poll: number | undefined;
let playerTimer: number | undefined;
let progressTimer: number | undefined;
let searchTimer: number | undefined;

const shown = computed(() => playlists.value.filter((p) => !filter.value || p.name.toLowerCase().includes(filter.value.toLowerCase())));
const linkRows = computed(() => state.value ? [
  ...state.value.ambiances.map((a) => ({ key: `ambiance:${a.key}`, label: `${t("Ambiance")} · ${a.label}` })),
  ...state.value.photo_playlists.map((p) => ({ key: `playlist:${p.id}`, label: `${t("Playlist de photos")} · ${p.name}` })),
] : []);
const fmt = (ms: number) => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

async function load() {
  state.value = await get<SpotifyState>("/api/spotify");
  clientId.value = state.value.client_id || "";
  if (!state.value.pending && poll) { window.clearInterval(poll); poll = undefined; }
  if (state.value.connected) {
    if (!playlists.value.length) loadPlaylists();
    if (!playerTimer) { loadPlayer(); playerTimer = window.setInterval(loadPlayer, 4000); }
  }
}
async function loadPlaylists() {
  try { playlists.value = (await get<{ playlists: Playlist[] }>("/api/spotify/playlists")).playlists; } catch (e) { notify((e as Error).message, true); }
}
async function loadPlayer() {
  try { player.value = await get<Player>("/api/spotify/player"); tick = Date.now(); } catch { player.value = null; }
}
function updateProgress() {
  const p = player.value;
  if (!p?.active || seeking.value) return;
  position.value = Math.min(p.track.duration_ms, p.progress_ms + (p.playing ? Date.now() - tick : 0));
}
async function action(name: string, value?: unknown) {
  const done = await run(() => post("/api/spotify/player", { action: name, value }));
  if (done) window.setTimeout(loadPlayer, 600);
  return done;
}
async function control(name: string) {
  await run(() => post("/api/spotify/control", { action: name }));
  window.setTimeout(loadPlayer, 700);
}
async function seek(event: Event) {
  const p = player.value;
  if (!p) return;
  const ms = Math.round((p.track.duration_ms * Number((event.target as HTMLInputElement).value)) / 1000);
  p.progress_ms = ms; tick = Date.now(); seeking.value = false;
  await action("seek", ms);
}
function search() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(async () => {
    if (query.value.trim().length < 2) { results.value = null; return; }
    try {
      const r = await get<{ tracks: Item[]; artists: Item[]; albums: Item[]; playlists: Item[] }>(`/api/spotify/search?q=${encodeURIComponent(query.value.trim())}`);
      results.value = { [t("Titres")]: r.tracks, [t("Artistes")]: r.artists, [t("Albums")]: r.albums, [t("Playlists")]: r.playlists };
    } catch (e) { notify((e as Error).message, true); }
  }, 400);
}
async function link() {
  notify(t("Demande de code à Spotify…"));
  const done = await run(() => post("/api/spotify/link"));
  if (done) { await load(); poll = window.setInterval(load, 3000); }
}
async function simple(url: string) { await run(() => post(url)); playlists.value = []; load(); }
async function saveClient() {
  const done = await run(() => post("/api/spotify/client_id", { client_id: clientId.value }));
  if (done) { showSetup.value = false; load(); }
}
async function copy(text: string) { try { await navigator.clipboard.writeText(text); notify(t("Copié.")); } catch { /* copie manuelle */ } }
async function setLink(key: string, uri: string) {
  await run(() => post("/api/spotify/links", { key, uri }));
  if (state.value) state.value.links[key] = uri;
}

onMounted(() => { load().catch(() => {}); progressTimer = window.setInterval(updateProgress, 1000); });
onUnmounted(() => { [poll, playerTimer, progressTimer].forEach((id) => window.clearInterval(id)); });
</script>

<template>
  <section v-if="state" class="card spotify">
    <div class="card-head"><h2><i class="fab fa-spotify"></i>Spotify</h2></div>

    <h3><span class="step">1</span>{{ t("Associer le cadre à votre compte") }}</h3>
    <p class="small muted">{{ t("Le cadre apparaît alors dans vos appareils Spotify, même quand vous n'êtes pas à la maison. Compte Premium nécessaire.") }}</p>
    <div v-if="state.linked" class="row">
      <span class="pill ok"><i class="fas fa-check"></i>{{ t("Associé") }}</span>
      <span v-if="state.account" class="small muted">{{ t("Compte :") }} {{ state.account }}</span>
      <button class="btn small" type="button" @click="simple('/api/spotify/unlink')">{{ t("Dissocier") }}</button>
    </div>
    <div v-else-if="state.pending" class="pairing">
      <p>{{ t("Ouvrez ce lien sur votre téléphone ou votre ordinateur, connectez-vous à Spotify et validez :") }}</p>
      <a v-if="state.url" class="btn primary" :href="state.url" target="_blank" rel="noopener"><i class="fas fa-external-link-alt"></i>spotify.com/pair</a>
      <p>{{ t("Code :") }} <strong class="code">{{ state.code }}</strong></p>
      <p class="small muted">{{ t("Cette page se met à jour toute seule une fois l'association validée.") }}</p>
    </div>
    <button v-else class="btn primary" type="button" @click="link"><i class="fab fa-spotify"></i>{{ t("Associer mon compte") }}</button>

    <h3><span class="step">2</span>{{ t("Choisir la musique depuis cette page") }}</h3>
    <div v-if="(!state.client_id && !state.connected) || showSetup" class="setup small">
      <p class="muted">{{ t("Une seule fois : Spotify demande de créer une « application » personnelle (gratuit, 5 minutes).") }}</p>
      <ol>
        <li>{{ t("Ouvrez") }} <a href="https://developer.spotify.com/dashboard" target="_blank" rel="noopener">developer.spotify.com/dashboard</a> {{ t("et cliquez sur « Create app ».") }}</li>
        <li>{{ t("Nom : Pimmich. Dans « Redirect URIs », collez cette adresse :") }}
          <span class="row"><code>{{ state.redirect_uri }}</code><button class="btn small" type="button" @click="copy(state.redirect_uri)">{{ t("Copier") }}</button></span>
          {{ t("Cochez « Web API », acceptez les conditions et enregistrez.") }}</li>
        <li>{{ t("Copiez le « Client ID » de l'application ici :") }}
          <span class="row"><input v-model="clientId" type="text" maxlength="32" placeholder="0123456789abcdef0123456789abcdef">
            <button class="btn small primary" type="button" @click="saveClient">{{ t("Enregistrer") }}</button></span></li>
      </ol>
      <p class="muted">{{ t("Ouvrez toujours l'interface avec la même adresse que celle déclarée ci-dessus (même adresse IP ou même nom).") }}</p>
    </div>
    <div v-if="state.client_id && !state.connected" class="row">
      <a class="btn primary" href="/spotify/login"><i class="fab fa-spotify"></i>{{ t("Se connecter à Spotify") }}</a>
      <button class="btn small" type="button" @click="showSetup = !showSetup">{{ t("Changer d'application") }}</button>
    </div>
    <div v-if="state.connected" class="row">
      <span class="pill ok"><i class="fas fa-check"></i>{{ t("Connecté") }}</span>
      <button class="btn small" type="button" @click="simple('/api/spotify/disconnect')">{{ t("Déconnecter") }}</button>
    </div>

    <template v-if="state.connected">
      <h3><i class="fas fa-play-circle"></i> {{ t("Lecture en cours") }}</h3>
      <p v-if="!player?.active" class="small muted">{{ t("Rien ne joue sur votre compte Spotify pour le moment : lancez une playlist ci-dessous ou recherchez un titre.") }}</p>
      <div v-else class="player">
        <img :src="player.track.image" alt="">
        <div class="spacer">
          <strong>{{ player.track.name }}</strong>
          <p class="small muted">{{ [player.track.artists, player.track.album].filter(Boolean).join(" · ") }}</p>
          <p class="small"><i class="fas fa-volume-up"></i> {{ t("sur") }} {{ player.device }}
            <button v-if="!player.on_frame" class="btn small" type="button" @click="action('transfer')">{{ t("Écouter sur le cadre") }}</button></p>
          <div class="seek"><span>{{ fmt(position) }}</span>
            <input type="range" min="0" max="1000" :value="player.track.duration_ms ? Math.round(1000 * position / player.track.duration_ms) : 0"
                   :aria-label="t('Avancement')" @input="seeking = true" @change="seek">
            <span>{{ fmt(player.track.duration_ms) }}</span></div>
          <div class="row">
            <button class="btn icon" :class="{ on: player.shuffle }" type="button" :title="t('Lecture aléatoire')" @click="action('shuffle', !player.shuffle)"><i class="fas fa-random"></i></button>
            <button class="btn icon" type="button" :title="t('Précédent')" @click="control('previous')"><i class="fas fa-step-backward"></i></button>
            <button class="btn icon primary" type="button" :title="t('Lecture / pause')" @click="control(player.playing ? 'pause' : 'resume')"><i class="fas" :class="player.playing ? 'fa-pause' : 'fa-play'"></i></button>
            <button class="btn icon" type="button" :title="t('Suivant')" @click="control('next')"><i class="fas fa-step-forward"></i></button>
            <button class="btn icon" :class="{ on: player.repeat !== 'off' }" type="button" :title="t('Répéter')"
                    @click="action('repeat', ({ off: 'context', context: 'track', track: 'off' } as Record<string, string>)[player.repeat] || 'off')">
              <i class="fas fa-redo"></i><small v-if="player.repeat === 'track'">1</small></button>
            <label v-if="player.volume !== null" class="vol"><i class="fas fa-volume-down"></i>
              <input type="range" min="0" max="100" step="5" :value="player.volume" :aria-label="t('Volume Spotify')" @change="action('volume', Number(($event.target as HTMLInputElement).value))"></label>
          </div>
        </div>
      </div>
      <template v-if="player?.active && player.queue.length">
        <h4>{{ t("À suivre sur Spotify") }}</h4>
        <ol class="items"><li v-for="q in player.queue" :key="q.uri"><img v-if="q.thumb" :src="q.thumb" alt=""><span><strong>{{ q.name }}</strong><small>{{ q.artists }}</small></span></li></ol>
      </template>

      <h3><i class="fas fa-search"></i> {{ t("Rechercher") }}</h3>
      <input v-model="query" type="search" class="field" :placeholder="t('Titre, artiste, album, playlist…')" @input="search">
      <template v-for="(items, title) in results || {}" :key="title">
        <template v-if="items.length">
          <h4>{{ title }}</h4>
          <ol class="items">
            <li v-for="i in items" :key="i.uri">
              <img v-if="i.thumb" :src="i.thumb" alt=""><span class="spacer"><strong>{{ i.name }}</strong><small>{{ i.artists }}</small></span>
              <button class="btn icon" type="button" :title="t('Écouter maintenant sur le cadre')" @click="action('play_uri', i.uri)"><i class="fas fa-play"></i></button>
              <button v-if="/^spotify:(track|episode):/.test(i.uri)" class="btn icon" type="button" :title="t('Ajouter à la file')"
                      @click="action('queue_uri', i.uri).then((ok) => ok && notify(t('Ajouté à la file d\'attente.')))"><i class="fas fa-plus"></i></button>
            </li>
          </ol>
        </template>
      </template>

      <h3><i class="fas fa-list"></i> {{ t("Lire sur le cadre") }}</h3>
      <input v-model="filter" type="search" class="field" :placeholder="t('Rechercher une playlist…')">
      <p v-if="!shown.length" class="small muted">{{ t("Aucune playlist trouvée.") }}</p>
      <div class="playlists">
        <button v-for="p in shown" :key="p.uri" type="button" class="pl" :title="t('Lire sur le cadre')" @click="run(() => post('/api/spotify/play', { uri: p.uri }))">
          <img v-if="p.image" :src="p.image" alt="" loading="lazy"><span v-else class="nocover"><i class="fas fa-music"></i></span>
          <span><strong>{{ p.name }}</strong><small>{{ p.tracks }} {{ t("titres") }}</small></span>
        </button>
      </div>

      <h3><i class="fas fa-link"></i> {{ t("Musiques associées") }}</h3>
      <p class="small muted">{{ t("Lancées automatiquement sur le cadre quand vous choisissez l'ambiance ou la playlist de photos.") }}</p>
      <div class="links">
        <label v-for="row in linkRows" :key="row.key">{{ row.label }}
          <select :value="state.links[row.key] || ''" @change="setLink(row.key, ($event.target as HTMLSelectElement).value)">
            <option value="">{{ t("Aucune musique") }}</option>
            <option v-for="p in playlists" :key="p.uri" :value="p.uri">{{ p.name }}</option>
          </select></label>
      </div>
    </template>
  </section>
</template>

<style scoped>
.spotify { margin-top: 1rem; }
.spotify .card-head i { color: #1db954; }
h3 { font-size: 1rem; margin: 1.1rem 0 .5rem; display: flex; gap: .5rem; align-items: center; }
h4 { font-size: .9rem; margin: .8rem 0 .3rem; }
.step { display: inline-grid; place-items: center; width: 1.5rem; height: 1.5rem; border-radius: 50%; background: var(--accent); color: var(--accent-text); font-size: .8rem; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.btn.on { color: var(--accent); border-color: var(--accent); }
.pairing { display: grid; gap: .5rem; }
.code { font-size: 1.4rem; letter-spacing: .1em; }
.setup ol { display: grid; gap: .6rem; padding-left: 1.2rem; }
.setup code { background: var(--surface-2); padding: .2rem .4rem; border-radius: 6px; word-break: break-all; }
.setup input, .field, .links select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; min-width: 0; }
.field { width: 100%; margin-bottom: .5rem; }
.player { display: flex; gap: 1rem; align-items: flex-start; flex-wrap: wrap; }
.player img { width: 120px; height: 120px; border-radius: 10px; object-fit: cover; }
.seek { display: flex; align-items: center; gap: .5rem; font-size: .8rem; margin: .4rem 0; }
.seek input { flex: 1; accent-color: var(--accent); }
.vol { display: flex; align-items: center; gap: .4rem; }
.vol input { width: 110px; accent-color: var(--accent); }
.items { list-style: none; padding: 0; margin: 0; display: grid; gap: .3rem; }
.items li { display: flex; align-items: center; gap: .6rem; }
.items img { width: 40px; height: 40px; border-radius: 6px; object-fit: cover; }
.items span { display: grid; min-width: 0; }
.items small { color: var(--muted); }
.items .btn.icon { width: 2.2rem; height: 2.2rem; }
.playlists { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .5rem; }
.pl { display: flex; gap: .6rem; align-items: center; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); color: var(--text); font: inherit; text-align: left; padding: .4rem; cursor: pointer; }
.pl:hover { background: var(--surface-2); }
.pl img, .nocover { width: 48px; height: 48px; border-radius: 8px; object-fit: cover; flex: none; display: grid; place-items: center; background: var(--surface-2); }
.pl span { display: grid; min-width: 0; }
.pl strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pl small { color: var(--muted); }
.links { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .6rem; }
.links label { display: grid; gap: .25rem; font-size: .88rem; font-weight: 600; }
</style>
