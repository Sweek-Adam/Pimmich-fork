<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

type State = "ok" | "missing" | "empty" | "stale";
interface Media { name: string; kind: "photo" | "video"; size: number; modified: number; state: State; prepared: string; error: string | null; queued: boolean; night?: boolean }
interface Source { source: string; label: string; items: Media[]; total: number; prepared: number }
interface Work {
  current: { name: string; kind: string; size: number | null; elapsed: number; index: number | null; total: number | null; step: string; percent: number | null; speed: string | null } | null;
  recent: { name: string; kind: string; size: number | null; ok: boolean; seconds: number; error: string | null }[];
  failed: { name: string; error: string | null }[];
}
interface ImportItem {
  source: string; label: string; phase: string; active: boolean; started: number; message: string; error: string | null;
  download: { percent: number; current: number; total: number }; prepare: { percent: number; current: number; total: number }; work: Work | null;
}

interface SpaceItem { source: string; label: string; name: string; kind: "photo" | "video"; size: number; estimate: number; gain: number; detail: string; cloud_copy: boolean; queued: boolean }
interface Space { items: SpaceItem[]; gain: number; saved: number; count: number; queue: { source: string; name: string }[] }

const imports = ref<ImportItem[]>([]);
const motion = ref<{ pending: number; running: boolean; enabled: boolean } | null>(null);
const space = ref<Space | null>(null);
const spaceLoading = ref(false);
const picked = reactive<Record<string, boolean>>({});
const keyOf = (i: { source: string; name: string }) => `${i.source}/${i.name}`;
const aloneHint = () => t("Pas d'autre copie que celle du cadre");
const sources = ref<Source[]>([]);
const loading = ref(true);
const filter = ref<"all" | "ready" | "todo" | "failed">("todo");
const search = ref("");
const shown = reactive<Record<string, number>>({});
const open = reactive<Record<string, boolean>>({});
const PAGE = 60;

const mb = (bytes: number | null | undefined) => bytes == null ? "" : bytes >= 1048576 ? `${(bytes / 1048576).toFixed(bytes >= 104857600 ? 0 : 1)} Mo` : `${Math.max(1, Math.round(bytes / 1024))} Ko`;
const duration = (s: number) => s < 60 ? `${Math.round(s)} s` : s < 3600 ? `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, "0")}` : `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`;
const stateLabel = (m: Media) => m.queued ? t("En file d'attente") : m.night && !m.error ? t("Prévue cette nuit") : ({ ok: t("Prêt"), missing: t("Pas préparé"), empty: t("Fichier préparé vide"), stale: t("Préparé pour une autre taille d'écran") }[m.state]);
const stateClass = (m: Media) => m.queued || (m.night && !m.error) ? "off" : m.state === "ok" ? "ok" : m.error ? "bad" : "warn";
const thumb = (source: string, m: Media) => m.state !== "ok" ? null
  : `/static/prepared/${encodeURIComponent(source)}/${encodeURIComponent(m.kind === "video" ? m.prepared.replace(/\.mp4$/, "_thumbnail.jpg") : m.prepared)}`;

const totals = computed(() => {
  const all = sources.value.flatMap((s) => s.items);
  return { all: all.length, ready: all.filter((m) => m.state === "ok").length, todo: all.filter((m) => m.state !== "ok").length,
           failed: all.filter((m) => m.state !== "ok" && m.error).length };
});
function visible(source: Source) {
  const q = search.value.trim().toLowerCase();
  return source.items.filter((m) => (filter.value === "all" || (filter.value === "ready" ? m.state === "ok" : filter.value === "failed" ? m.state !== "ok" && !!m.error : m.state !== "ok"))
    && (!q || m.name.toLowerCase().includes(q)));
}
const listed = computed(() => sources.value.map((s) => ({ ...s, list: visible(s) })).filter((s) => s.list.length));

async function loadInventory() {
  try {
    sources.value = (await get<{ sources: Source[] }>("/api/media/inventory")).sources;
  } finally {
    loading.value = false;
  }
}
async function loadImports() {
  try { imports.value = (await get<{ imports: ImportItem[] }>("/api/imports/progress")).imports; } catch { /* hors ligne : on réessaie */ }
}
async function prepare(source: string, names: string[]) {
  if (!names.length) return;
  const r = await run(() => post("/api/media/prepare", { source, names }));
  if (r?.success) {
    const set = new Set(names);
    sources.value.find((s) => s.source === source)?.items.forEach((m) => { if (set.has(m.name)) m.queued = true; });
    loadImports();
  }
}
async function loadMotion() {
  try { motion.value = await get<{ pending: number; running: boolean; enabled: boolean }>("/api/media/motion"); } catch { motion.value = null; }
}
async function makeMotion() {
  const r = await run(() => post("/api/media/motion"));
  if (r?.success && motion.value) motion.value.running = true;
}
async function analyseSpace() {
  spaceLoading.value = true;
  try {
    space.value = await get<Space>("/api/media/space");
    for (const i of space.value.items) picked[keyOf(i)] = !i.queued;
  } finally {
    spaceLoading.value = false;
  }
}
const pickedItems = computed(() => (space.value?.items ?? []).filter((i) => picked[keyOf(i)] && !i.queued));
const pickedGain = computed(() => pickedItems.value.reduce((n, i) => n + i.gain, 0));
async function reduce() {
  const items = pickedItems.value;
  if (!items.length) return;
  const alone = items.filter((i) => !i.cloud_copy).length;
  const warning = alone
    ? t("{count} de ces médias n'existent que sur le cadre (téléphone, invités, Telegram...) : leur original sera remplacé par la version réduite, sans retour possible.", { count: alone })
    : t("Les originaux restent disponibles dans leur source (Google Drive, Immich...).");
  if (!window.confirm(`${t("Remplacer {count} original(aux) par une version réduite ?", { count: items.length })}\n\n${warning}`)) return;
  await run(() => post("/api/media/reduce", { items: items.map((i) => ({ source: i.source, name: i.name })) }));
  analyseSpace();
}
const missingNames = (s: Source) => s.items.filter((m) => m.state !== "ok" && !m.queued).map((m) => m.name);

let timer: number | undefined;
let wasActive = false;
onMounted(() => {
  loadInventory();
  loadImports();
  loadMotion();
  timer = window.setInterval(async () => {
    await loadImports();
    const active = imports.value.some((i) => i.active);
    if (wasActive && !active) loadInventory();  // une préparation vient de finir : états à jour
    if (motion.value?.running) loadMotion();
    wasActive = active;
  }, 2000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section class="card" id="en-cours">
    <div class="card-head"><h2><i class="fas fa-cogs"></i>{{ t("Préparation en cours") }}</h2></div>
    <p v-if="!imports.length" class="muted">{{ t("Aucun import ni préparation en cours.") }}</p>
    <div v-for="item in imports" :key="item.source" class="job">
      <div class="job-head">
        <i class="fas" :class="item.active ? 'fa-sync-alt fa-spin' : 'fa-check-circle'"></i>
        <strong>{{ item.label }}</strong>
        <span class="muted small">{{ item.phase === "prepare" ? t("préparation") : t("téléchargement") }} · {{ t("depuis") }} {{ duration(Date.now() / 1000 - item.started) }}</span>
        <span class="spacer"></span>
        <strong>{{ item.phase === "prepare" ? item.prepare.percent : item.download.percent }}%</strong>
      </div>
      <div class="bar"><span :style="{ width: (item.phase === 'prepare' ? item.prepare.percent : item.download.percent) + '%' }"></span></div>
      <p class="small muted" v-if="item.phase === 'prepare' && item.prepare.total">
        {{ t("{done} médias sur {total} préparés", { done: item.prepare.current, total: item.prepare.total }) }}</p>
      <p class="small muted" v-else-if="item.message">{{ item.message }}</p>
      <p v-if="item.error" class="small error-text">{{ item.error }}</p>

      <div v-if="item.work?.current" class="now">
        <i class="fas" :class="item.work.current.kind === 'video' ? 'fa-film' : 'fa-image'"></i>
        <div class="now-body">
          <div class="now-name" :title="item.work.current.name">{{ item.work.current.name }}</div>
          <div class="small muted">
            <span v-if="item.work.current.index">{{ item.work.current.index }}/{{ item.work.current.total }} · </span>
            {{ mb(item.work.current.size) }} · {{ item.work.current.kind === "video" ? t("encodage vidéo") : t("photo") }} · {{ duration(item.work.current.elapsed) }}
            <span v-if="item.work.current.speed"> · {{ item.work.current.speed }}</span>
          </div>
          <div v-if="item.work.current.percent !== null" class="bar thin"><span :style="{ width: item.work.current.percent + '%' }"></span></div>
          <div v-if="item.work.current.percent !== null" class="small muted">{{ t("Vidéo encodée à {percent} %", { percent: item.work.current.percent }) }}</div>
        </div>
      </div>
      <details v-if="item.work?.recent.length" class="recent">
        <summary class="small">{{ t("Derniers médias traités") }} ({{ item.work.recent.length }})</summary>
        <ul>
          <li v-for="r in item.work.recent" :key="r.name + r.seconds">
            <i class="fas" :class="r.ok ? 'fa-check ok-text' : 'fa-times error-text'"></i>
            <span class="name">{{ r.name }}</span><span class="small muted">{{ mb(r.size) }} · {{ duration(r.seconds) }}</span>
            <div v-if="r.error" class="small error-text">{{ r.error }}</div>
          </li>
        </ul>
      </details>
    </div>
  </section>

  <section v-if="motion && motion.enabled && (motion.pending || motion.running)" class="card">
    <div class="card-head"><h2><i class="fas fa-play-circle"></i>{{ t("Photos animées") }}</h2>
      <button class="btn small primary" type="button" :disabled="motion.running" @click="makeMotion">
        <i class="fas" :class="motion.running ? 'fa-spinner fa-spin' : 'fa-magic'"></i> {{ motion.running ? t("Création en cours...") : t("Créer maintenant") }}</button></div>
    <p class="small muted">{{ t("{count} photo(s) animée(s) de téléphone attendent leur animation (créée automatiquement cette nuit).", { count: motion.pending }) }}</p>
  </section>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-compress-arrows-alt"></i>{{ t("Gagner de la place") }}</h2>
      <button class="btn small" type="button" :disabled="spaceLoading" @click="analyseSpace">
        <i class="fas" :class="spaceLoading ? 'fa-spinner fa-spin' : 'fa-search'"></i> {{ space ? t("Actualiser") : t("Analyser") }}</button></div>
    <p class="small muted">{{ t("Les très grosses photos (plus de 4096 px) et vidéos (plus de 100 Mo) déjà prêtes peuvent être remplacées par une version réduite, toujours plus grande que l'écran : photos en 4096 px avec leurs données (date, lieu), vidéos en 1080p, réencodées la nuit.") }}</p>
    <template v-if="space">
      <p v-if="space.count" class="small ok-text">{{ t("Déjà gagné : {size} ({count} médias réduits).", { size: mb(space.saved), count: space.count }) }}</p>
      <p v-if="!space.items.length" class="muted">{{ t("Aucun média ne gagnerait à être réduit.") }}</p>
      <template v-else>
        <div class="space-head">
          <strong>{{ t("{count} médias, jusqu'à {size} à gagner", { count: space.items.length, size: mb(space.gain) }) }}</strong>
          <span class="spacer"></span>
          <button class="btn small primary" type="button" :disabled="!pickedItems.length" @click="reduce">
            <i class="fas fa-compress"></i> {{ t("Réduire la sélection ({size})", { size: mb(pickedGain) }) }}</button>
        </div>
        <ul class="items">
          <li v-for="i in space.items.slice(0, 200)" :key="keyOf(i)">
            <input type="checkbox" v-model="picked[keyOf(i)]" :disabled="i.queued" :aria-label="i.name">
            <span class="thumb"><i class="fas" :class="i.kind === 'video' ? 'fa-film' : 'fa-image'"></i></span>
            <div class="item-body">
              <div class="name" :title="i.name">{{ i.name }}</div>
              <div class="small muted">{{ i.label }} · {{ i.detail }} · {{ mb(i.size) }} → ~{{ mb(i.estimate) }}</div>
            </div>
            <span v-if="i.queued" class="pill off">{{ t("Prévue cette nuit") }}</span>
            <span v-else-if="!i.cloud_copy" class="pill warn" :title="aloneHint()">{{ t("Seul exemplaire") }}</span>
          </li>
        </ul>
      </template>
    </template>
  </section>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-photo-video"></i>{{ t("Médias du cadre") }}</h2>
      <button class="btn icon" type="button" :title="t('Actualiser')" @click="loadInventory"><i class="fas fa-sync-alt"></i></button></div>
    <p class="small muted">{{ t("Tous les médias reçus, source par source. Un média « pas préparé » n'apparaît pas sur le cadre : le bouton Préparer le rattrape (import interrompu, ancien bug...).") }}</p>
    <div class="filters">
      <button v-for="f in ([['todo', t('À préparer'), totals.todo], ['failed', t('En échec'), totals.failed], ['ready', t('Préparés'), totals.ready], ['all', t('Tous'), totals.all]] as const)"
              :key="f[0]" type="button" class="chip" :class="{ on: filter === f[0] }" @click="filter = f[0]">{{ f[1] }} <b>{{ f[2] }}</b></button>
      <input v-model="search" type="search" class="search" :placeholder="t('Rechercher un fichier')">
    </div>
    <p v-if="loading" class="muted">{{ t("Chargement...") }}</p>
    <p v-else-if="!listed.length" class="muted">{{ filter === "todo" ? t("Tous les médias sont préparés.") : t("Aucun média.") }}</p>

    <div v-for="s in listed" :key="s.source" class="source">
      <div class="source-head" @click="open[s.source] = !open[s.source]">
        <i class="fas" :class="open[s.source] === false ? 'fa-chevron-right' : 'fa-chevron-down'"></i>
        <strong>{{ s.label }}</strong>
        <span class="small muted">{{ t("{prepared} préparés sur {total}", { prepared: s.prepared, total: s.total }) }}</span>
        <span class="spacer"></span>
        <button v-if="missingNames(s).length" class="btn small primary" type="button" @click.stop="prepare(s.source, missingNames(s))">
          <i class="fas fa-play"></i> {{ t("Préparer les {count} manquants", { count: missingNames(s).length }) }}</button>
      </div>
      <ul v-if="open[s.source] !== false" class="items">
        <li v-for="m in s.list.slice(0, shown[s.source] || PAGE)" :key="m.name">
          <span class="thumb">
            <img v-if="thumb(s.source, m)" :src="thumb(s.source, m)!" loading="lazy" alt="">
            <i v-else class="fas" :class="m.kind === 'video' ? 'fa-film' : 'fa-image'"></i>
          </span>
          <div class="item-body">
            <div class="name" :title="m.name">{{ m.name }}</div>
            <div class="small muted">{{ mb(m.size) }} · {{ new Date(m.modified * 1000).toLocaleDateString() }}</div>
            <div v-if="m.error" class="small error-text" :title="m.error">{{ m.error }}</div>
          </div>
          <span class="pill" :class="stateClass(m)">{{ stateLabel(m) }}</span>
          <button v-if="m.state !== 'ok' && !m.queued" class="btn small" type="button" @click="prepare(s.source, [m.name])">{{ t("Préparer") }}</button>
        </li>
      </ul>
      <button v-if="open[s.source] !== false && s.list.length > (shown[s.source] || PAGE)" class="btn small more" type="button"
              @click="shown[s.source] = (shown[s.source] || PAGE) + PAGE">{{ t("Afficher plus") }} ({{ s.list.length - (shown[s.source] || PAGE) }})</button>
    </div>
  </section>
</template>

<style scoped>
.job + .job { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); }
.job-head, .source-head { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.job-head i { color: var(--accent); }
.spacer { flex: 1; }
.bar { height: 8px; border-radius: 999px; background: var(--surface-2); overflow: hidden; margin: .5rem 0 .3rem; }
.bar.thin { height: 5px; }
.bar span { display: block; height: 100%; background: var(--accent); border-radius: inherit; transition: width .6s; }
.now { display: flex; gap: .75rem; align-items: flex-start; margin-top: .6rem; padding: .7rem .8rem; border-radius: 12px; background: var(--surface-2); }
.now > i { font-size: 1.3rem; color: var(--accent); margin-top: .15rem; }
.now-body { min-width: 0; flex: 1; }
.now-name, .name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent { margin-top: .6rem; }
.recent summary { cursor: pointer; color: var(--muted); }
.recent ul, .items { list-style: none; padding: 0; margin: .4rem 0 0; display: grid; gap: .35rem; }
.recent li { display: flex; flex-wrap: wrap; gap: .5rem; align-items: baseline; }
.recent li .name { max-width: 60%; }
.ok-text { color: var(--ok); }
.error-text { color: var(--danger); overflow-wrap: anywhere; }
.filters { display: flex; flex-wrap: wrap; gap: .4rem; align-items: center; margin: .6rem 0 .8rem; }
.chip { border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: 999px; padding: .3rem .8rem; font: inherit; font-size: .85rem; cursor: pointer; }
.chip.on { border-color: var(--accent); background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.search { flex: 1 1 180px; min-width: 0; }
.source { border-top: 1px solid var(--border); padding: .75rem 0; }
.source-head { cursor: pointer; }
.items li { display: flex; align-items: center; gap: .6rem; padding: .35rem 0; }
.thumb { flex: none; width: 52px; height: 36px; border-radius: 6px; background: var(--surface-2); display: grid; place-items: center; overflow: hidden; color: var(--muted); }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.item-body { min-width: 0; flex: 1; }
.pill.bad { background: var(--danger-soft); color: var(--danger); }
.btn.small { padding: .3rem .7rem; font-size: .82rem; }
.more { margin-top: .4rem; }
.space-head { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; margin: .5rem 0; }
@media (max-width: 560px) { .items li { flex-wrap: wrap; } .items .pill { margin-left: 60px; } }
</style>
