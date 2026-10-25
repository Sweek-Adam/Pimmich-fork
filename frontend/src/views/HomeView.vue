<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { get, post } from "../api";
import { boot, classicUrl } from "../boot";
import { t } from "../i18n";
import { routeForTab } from "../nav";
import { run } from "../toast";
import { unseen } from "../news";

interface Health { level: "warning" | "error" | "info"; title: string; detail: string; tab?: string }
interface Step { key: string; title: string; done: boolean; tab: string }
interface Ambiance { key: string; label: string; description: string; icon: string; active: boolean }
interface Track { title: string; artist: string; cover?: string; playing: boolean; source_label: string }
interface Music { track: Track | null; actions: string[]; hint?: string; muted: boolean }
interface QueueItem { thumb: string; video: boolean; name: string }
interface HistoryEvent { id: string; at: number; text: string; who: string; undoable?: boolean; undone?: boolean }

const router = useRouter();
const fresh = unseen();
const status = ref<{ running: boolean; paused: boolean }>({ running: false, paused: false });
const photo = ref<string | null>(null);
const health = ref<Health[]>([]);
const setup = ref<{ steps: Step[]; dismissed: boolean; done: number } | null>(null);
const ambiances = ref<Ambiance[]>([]);
const music = ref<Music | null>(null);
const upcoming = ref<QueueItem[]>([]);
const memories = ref<{ thumb: string; years_ago: number }[]>([]);
const events = ref<HistoryEvent[]>([]);
const undo = ref<HistoryEvent | null>(null);
const busy = ref(false);
const media = ref<{ mode: string; videos: number }>({ mode: "all", videos: 0 });
let timer: number | undefined;

const setupLeft = computed(() => setup.value?.steps.filter((s) => !s.done) ?? []);

async function refreshNow() {
  const [s, current, queue] = await Promise.allSettled([
    get<{ running: boolean; paused: boolean }>("/api/slideshow/status"),
    get<{ current_photo: string | null }>("/current_photo_status"),
    get<{ upcoming: QueueItem[] }>("/api/slideshow/queue"),
  ]);
  if (s.status === "fulfilled") status.value = s.value;
  if (current.status === "fulfilled") photo.value = current.value.current_photo;
  if (queue.status === "fulfilled") upcoming.value = queue.value.upcoming.slice(0, 8);
}

async function refreshMusic() {
  try {
    music.value = await get<Music>("/api/music/remote");
  } catch {
    music.value = null;
  }
}

async function loadAll() {
  refreshNow();
  refreshMusic();
  get<{ items: Health[] }>("/api/health").then((d) => (health.value = d.items)).catch(() => {});
  get<{ steps: Step[]; dismissed: boolean; done: number }>("/api/setup").then((d) => (setup.value = d)).catch(() => {});
  get<{ mode: string; videos: number }>("/api/slideshow/media_mode").then((d) => (media.value = d)).catch(() => {});
  get<{ ambiances: Ambiance[] }>("/api/ambiances").then((d) => (ambiances.value = d.ambiances)).catch(() => {});
  get<{ items: { thumb: string; years_ago: number }[] }>("/api/memories/today").then((d) => (memories.value = d.items)).catch(() => {});
  loadHistory();
}

async function loadHistory() {
  try {
    const d = await get<{ events: HistoryEvent[]; undo: HistoryEvent | null }>("/api/history?limit=6");
    events.value = d.events;
    undo.value = d.undo;
  } catch {
    events.value = [];
  }
}

async function control(action: "previous" | "next" | "toggle_pause" | "toggle_sleep") {
  busy.value = true;
  await run(() => post(`/api/slideshow/${action}`));
  busy.value = false;
  document.dispatchEvent(new Event("pimmich:status"));
  window.setTimeout(refreshNow, action === "toggle_sleep" ? 2500 : 800);
}

async function setMediaMode(mode: string) {
  const done = await run(() => post("/api/slideshow/media_mode", { mode }));
  if (done) media.value = { ...media.value, mode };
  document.dispatchEvent(new Event("pimmich:status"));
  window.setTimeout(refreshNow, 2500);
  loadHistory();
}

async function chooseAmbiance(key: string) {
  const done = await run(() => post("/api/ambiance", { ambiance: key }));
  if (done) ambiances.value = ambiances.value.map((a) => ({ ...a, active: a.key === key }));
  loadHistory();
}

async function musicAction(action: string) {
  await run(() => post("/api/music/remote", { action }));
  window.setTimeout(refreshMusic, 700);
}

async function undoLast() {
  await run(() => post("/api/history/undo"));
  loadHistory();
}

async function dismissSetup() {
  await run(() => post("/api/setup/dismiss"));
  if (setup.value) setup.value.dismissed = true;
}

async function shutdown() {
  if (!window.confirm(t("Éteindre complètement le Raspberry Pi ? Il faudra débrancher puis rebrancher l'alimentation pour le rallumer."))) return;
  await run(() => post("/api/system/shutdown"));
}

function openTab(tab?: string) {
  const route = tab ? routeForTab(tab) : undefined;
  if (route) router.push(route);
  else window.location.href = classicUrl(tab);
}

function when(at: number) {
  const date = new Date(at * 1000);
  const today = new Date().toDateString() === date.toDateString();
  return today ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : date.toLocaleDateString();
}

const musicIcons: Record<string, string> = { previous: "fa-step-backward", play_pause: "fa-play", pause: "fa-pause", play: "fa-play", next: "fa-step-forward" };

onMounted(() => {
  loadAll();
  timer = window.setInterval(() => { refreshNow(); refreshMusic(); }, 10000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <div class="home">
    <router-link v-if="fresh.length" to="/nouveautes" class="card news-banner">
      <i class="fas fa-gift"></i>
      <span><strong>{{ t("{count} nouveauté(s) sur le cadre", { count: fresh.length }) }}</strong>
        <span class="small muted"> · {{ fresh.slice(0, 3).map((n) => n.title()).join(" · ") }}</span></span>
      <span class="spacer"></span><i class="fas fa-chevron-right"></i>
    </router-link>
    <section class="card now">
      <div class="screen" :class="{ off: !status.running }">
        <img v-if="photo && status.running" :src="photo" alt="">
        <div v-else class="screen-off"><i class="fas fa-moon"></i><span>{{ t("Le cadre est en veille") }}</span></div>
      </div>
      <div class="controls">
        <button class="btn icon big" type="button" :disabled="busy || !status.running" :title="t('Photo précédente')" @click="control('previous')">
          <i class="fas fa-step-backward"></i></button>
        <button class="btn icon big primary" type="button" :disabled="busy || !status.running" :title="status.paused ? t('Reprendre') : t('Pause')" @click="control('toggle_pause')">
          <i class="fas" :class="status.paused ? 'fa-play' : 'fa-pause'"></i></button>
        <button class="btn icon big" type="button" :disabled="busy || !status.running" :title="t('Photo suivante')" @click="control('next')">
          <i class="fas fa-step-forward"></i></button>
        <span class="spacer"></span>
        <button class="btn" type="button" :disabled="busy" @click="control('toggle_sleep')">
          <i class="fas fa-moon"></i>{{ status.running ? t("Mettre en veille") : t("Allumer le cadre") }}</button>
        <button v-if="boot.admin" class="btn danger" type="button" :title="t('Éteindre le Raspberry Pi')" @click="shutdown">
          <i class="fas fa-power-off"></i>{{ t("Éteindre") }}</button>
      </div>
      <div class="modes">
        <button type="button" class="mode" :class="{ on: media.mode !== 'videos' }" @click="setMediaMode('all')">
          <i class="fas fa-images"></i>{{ t("Photos et vidéos") }}</button>
        <button type="button" class="mode" :class="{ on: media.mode === 'videos' }" :disabled="!media.videos" @click="setMediaMode('videos')">
          <i class="fas fa-film"></i>{{ t("Vidéos seulement") }} <span class="small">({{ media.videos }})</span></button>
      </div>
      <div v-if="upcoming.length" class="upcoming">
        <p class="small muted">{{ t("À suivre") }}</p>
        <div class="strip">
          <img v-for="item in upcoming" :key="item.thumb" :src="item.thumb" :alt="item.name" loading="lazy">
        </div>
      </div>
    </section>

    <div class="side">
      <section v-if="health.length" class="card">
        <div class="card-head"><h2><i class="fas fa-heartbeat"></i>{{ t("État du cadre") }}</h2></div>
        <div v-for="item in health" :key="item.title" class="alert" :class="item.level">
          <i class="fas" :class="item.level === 'info' ? 'fa-info-circle' : 'fa-exclamation-triangle'"></i>
          <div class="spacer">
            <strong>{{ item.title }}</strong>
            <p class="small">{{ item.detail }}</p>
          </div>
          <button v-if="item.tab" class="btn icon" type="button" :title="t('Ouvrir')" @click="openTab(item.tab)"><i class="fas fa-chevron-right"></i></button>
        </div>
      </section>

      <section v-if="setup && !setup.dismissed && setupLeft.length" class="card">
        <div class="card-head">
          <h2><i class="fas fa-flag-checkered"></i>{{ t("Bien démarrer") }}</h2>
          <button class="btn small" type="button" @click="dismissSetup">{{ t("Masquer") }}</button>
        </div>
        <div class="steps">
          <button v-for="step in setup.steps" :key="step.key" type="button" class="step" :class="{ done: step.done }" @click="openTab(step.tab)">
            <i class="fas" :class="step.done ? 'fa-check-circle' : 'fa-circle'"></i>{{ step.title }}
          </button>
        </div>
      </section>

      <section v-if="music && music.track" class="card music">
        <img v-if="music.track.cover" :src="music.track.cover" alt="" class="cover">
        <div class="spacer">
          <p class="small muted">{{ music.track.source_label }}</p>
          <strong>{{ music.track.title }}</strong>
          <p class="muted">{{ music.track.artist }}</p>
          <div v-if="music.actions.length" class="row">
            <button v-for="action in music.actions" :key="action" class="btn icon" type="button" @click="musicAction(action)">
              <i class="fas" :class="musicIcons[action] || 'fa-music'"></i></button>
          </div>
          <p v-else-if="music.hint" class="small muted">{{ music.hint }}</p>
        </div>
      </section>
    </div>

    <section class="card wide">
      <div class="card-head"><h2><i class="fas fa-palette"></i>{{ t("Ambiance") }}</h2></div>
      <div class="ambiances">
        <button v-for="a in ambiances" :key="a.key" type="button" class="ambiance" :class="{ active: a.active }" @click="chooseAmbiance(a.key)">
          <i class="fas" :class="a.icon"></i>
          <strong>{{ a.label }}</strong>
          <span class="small muted">{{ a.description }}</span>
        </button>
      </div>
    </section>

    <section v-if="memories.length" class="card wide">
      <div class="card-head"><h2><i class="fas fa-history"></i>{{ t("Ce jour-là") }}</h2></div>
      <div class="thumbs">
        <figure v-for="m in memories" :key="m.thumb" class="memory">
          <img :src="m.thumb" alt="" loading="lazy">
          <figcaption>{{ m.years_ago === 1 ? t("Il y a un an") : t("Il y a {n} ans", { n: m.years_ago }) }}</figcaption>
        </figure>
      </div>
    </section>

    <section class="card wide">
      <div class="card-head">
        <h2><i class="fas fa-clock"></i>{{ t("Dernières actions") }}</h2>
        <button v-if="undo" class="btn" type="button" @click="undoLast"><i class="fas fa-undo"></i>{{ t("Annuler") }}</button>
      </div>
      <p v-if="!events.length" class="muted">{{ t("Rien pour l'instant.") }}</p>
      <ul class="events">
        <li v-for="e in events" :key="e.id" :class="{ undone: e.undone }">
          <span class="muted small">{{ when(e.at) }}</span>
          <span class="spacer">{{ e.text }}</span>
          <span v-if="e.who" class="muted small">{{ e.who }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.home { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 1rem; align-items: start; }
.wide { grid-column: 1 / -1; }
.side { display: grid; gap: 1rem; }
.side .card + .card { margin-top: 0; }
.home > .card + .card { margin-top: 0; }
@media (max-width: 1000px) { .home { grid-template-columns: minmax(0, 1fr); } }

.screen { aspect-ratio: 16 / 9; border-radius: 12px; overflow: hidden; background: #0d0f14; display: grid; place-items: center; }
.screen img { width: 100%; height: 100%; object-fit: contain; }
.screen-off { color: #8a90a6; display: flex; flex-direction: column; align-items: center; gap: .5rem; font-weight: 500; }
.screen-off i { font-size: 2rem; }
.controls { display: flex; align-items: center; gap: .6rem; margin-top: .9rem; flex-wrap: wrap; }
.upcoming { margin-top: .9rem; }
.modes { display: flex; gap: .3rem; margin-top: .9rem; background: var(--surface-2); padding: .25rem; border-radius: 999px; width: fit-content; max-width: 100%; }
.mode { border: 0; background: none; color: var(--muted); font: inherit; font-weight: 600; padding: .4rem .9rem; border-radius: 999px; cursor: pointer; display: flex; gap: .4rem; align-items: center; }
.mode.on { background: var(--surface); color: var(--accent); box-shadow: var(--shadow); }
.mode:disabled { opacity: .45; cursor: default; }
.strip { display: flex; gap: .4rem; overflow-x: auto; padding-bottom: .2rem; margin-top: .3rem; }
.strip img { width: 88px; height: 60px; object-fit: cover; border-radius: 8px; flex: none; }

.steps { display: grid; gap: .3rem; }
.step { display: flex; align-items: center; gap: .6rem; text-align: left; border: 0; background: none; font: inherit; color: var(--text); padding: .35rem .2rem; border-radius: 8px; cursor: pointer; }
.step:hover { background: var(--surface-2); }
.step i { color: var(--muted); }
.step.done { color: var(--muted); text-decoration: line-through; }
.step.done i { color: var(--ok); }
.btn.small { padding: .25rem .7rem; font-size: .8rem; }

.music { display: flex; gap: 1rem; align-items: center; }
.cover { width: 88px; height: 88px; border-radius: 10px; object-fit: cover; flex: none; }
.music .row { margin-top: .4rem; }

.ambiances { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(150px, 45%), 1fr)); gap: .6rem; }
.ambiance {
  display: flex; flex-direction: column; align-items: flex-start; gap: .2rem; text-align: left; font: inherit; color: var(--text);
  background: var(--surface-2); border: 2px solid transparent; border-radius: 14px; padding: .8rem; cursor: pointer;
}
.ambiance i { color: var(--accent); font-size: 1.1rem; margin-bottom: .2rem; }
.ambiance:hover { border-color: var(--border); }
.ambiance.active { border-color: var(--accent); background: var(--accent-soft); }

.memory { margin: 0; position: relative; }
.memory figcaption { position: absolute; left: 6px; bottom: 6px; background: rgba(0, 0, 0, .6); color: #fff; font-size: .72rem; padding: 1px 7px; border-radius: 999px; }

.events { list-style: none; margin: 0; padding: 0; }
.events li { display: flex; gap: .8rem; align-items: baseline; padding: .45rem 0; border-bottom: 1px solid var(--border); }
.events li:last-child { border-bottom: 0; }
.events li.undone .spacer { text-decoration: line-through; color: var(--muted); }
.news-banner { display: flex; align-items: center; gap: .7rem; text-decoration: none; color: var(--text); border-color: var(--accent); margin-bottom: 1rem; }
.news-banner > i:first-child { color: var(--accent); font-size: 1.3rem; }
.news-banner .spacer { flex: 1; }
</style>
