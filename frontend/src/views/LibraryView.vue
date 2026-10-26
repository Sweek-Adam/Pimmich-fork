<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { get, post } from "../api";
import { currentLang, t } from "../i18n";
import { notify, run } from "../toast";
import CaptionEditor from "../components/CaptionEditor.vue";
import PhotoBookCard from "../components/PhotoBookCard.vue";
import VoiceMemo from "../components/VoiceMemo.vue";
import PhotoComments from "../components/PhotoComments.vue";

const props = defineProps<{ favorites?: boolean }>();

interface Item {
  path: string; thumb: string; url: string; date: string | null; place?: string | null; people: string[];
  caption?: string | null; video: boolean; favorite: boolean; source: string; voice?: number | null;
  suggestion?: { caption?: string; tags?: string[] } | null;
}

const filters = reactive({ q: "", source: "", person: "", media: "", from: "", to: "", fav: !!props.favorites, smart: false });
const smartAvailable = ref(false);
const smartHint = () => t("Recherche par contenu grâce à l'analyse des images d'Immich (photos importées d'Immich)");
const items = ref<Item[]>([]);
const total = ref(0);
const loading = ref(true);
const sources = ref<string[]>([]);
const people = ref<{ id: string; name: string }[]>([]);
const open = ref<number | null>(null);
const captionText = ref("");
const styling = ref(false);
let debounce: number | undefined;

const current = computed(() => (open.value === null ? null : items.value[open.value]));
const sourceLabel = (s: string) => (s.startsWith("compte_") ? s.slice(7) : s);
const dateLabel = (d: string | null) =>
  d ? new Date(d).toLocaleDateString(currentLang(), { day: "numeric", month: "long", year: "numeric" }) : "";

async function search() {
  loading.value = true;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (key === "fav" || key === "smart") { if (value) params.set(key, "1"); }
    else if (value) params.set(key, String(value));
  }
  try {
    const d = await get<{ items: Item[]; total: number; smart_available?: boolean }>(`/api/library/search?${params}`);
    smartAvailable.value = !!d.smart_available;
    items.value = d.items;
    total.value = d.total;
  } catch (e) {
    notify((e as Error).message, true);
  }
  loading.value = false;
}

watch(filters, () => {
  window.clearTimeout(debounce);
  debounce = window.setTimeout(search, 300);
});

async function toggleFavorite(item: Item) {
  try {
    const d = await post<{ success: boolean; is_favorite: boolean }>("/api/toggle_favorite", { photo: item.path });
    item.favorite = d.is_favorite;
    notify(d.is_favorite ? t("Ajoutée aux favoris.") : t("Retirée des favoris."));
    if (filters.fav && !d.is_favorite) {
      items.value = items.value.filter((i) => i !== item);
      total.value -= 1;
      if (open.value !== null && open.value >= items.value.length) open.value = items.value.length ? items.value.length - 1 : null;
    }
  } catch (e) {
    notify((e as Error).message, true);
  }
}

watch(open, () => { captionText.value = current.value?.caption || ""; });

async function colorizePhoto(item: Item) { await run(() => post("/api/colorize", { path: item.path })); }
async function saveCaption(item: Item) {
  const done = await run(() => post<{ message?: string }>("/api/set_image_text", { photo: item.path, text: captionText.value }), t("Légende enregistrée."));
  if (done) { item.caption = captionText.value; item.url = item.url.split("?")[0] + `?v=${Date.now()}`; item.thumb = item.thumb.split("?")[0] + `?v=${Date.now()}`; }
}

function step(delta: number) {
  if (open.value === null || !items.value.length) return;
  open.value = (open.value + delta + items.value.length) % items.value.length;
}

function onKey(event: KeyboardEvent) {
  if (open.value === null || styling.value || (event.target as HTMLElement).tagName === "INPUT") return;
  if (event.key === "ArrowRight") step(1);
  else if (event.key === "ArrowLeft") step(-1);
  else if (event.key === "Escape") open.value = null;
}

function reset() {
  Object.assign(filters, { q: "", source: "", person: "", media: "", from: "", to: "", fav: !!props.favorites });
}

onMounted(async () => {
  search();
  window.addEventListener("keydown", onKey);
  get<{ sources: Record<string, unknown> }>("/api/stats/photos").then((d) => (sources.value = Object.keys(d.sources).sort())).catch(() => {});
  get<{ people: { id: string; name: string }[] }>("/api/people").then((d) => (people.value = d.people)).catch(() => {});
});
onUnmounted(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <section class="card">
    <form class="filters" @submit.prevent="search">
      <label class="search"><i class="fas fa-search"></i>
        <input v-model="filters.q" type="search" :placeholder="filters.smart ? t('Décrivez la photo : plage, chien, neige…') : t('Rechercher (lieu, légende, nom de fichier…)')"></label>
      <label v-if="smartAvailable" class="smart" :title="smartHint()">
        <input v-model="filters.smart" type="checkbox"> {{ t("Par contenu (Immich)") }}</label>
      <select v-model="filters.source">
        <option value="">{{ t("Toutes les sources") }}</option>
        <option v-for="s in sources" :key="s" :value="s">{{ sourceLabel(s) }}</option>
      </select>
      <select v-if="people.length" v-model="filters.person">
        <option value="">{{ t("Tout le monde") }}</option>
        <option v-for="p in people" :key="p.id" :value="p.name">{{ p.name }}</option>
      </select>
      <select v-model="filters.media">
        <option value="">{{ t("Photos et vidéos") }}</option>
        <option value="photos">{{ t("Photos") }}</option>
        <option value="videos">{{ t("Vidéos") }}</option>
      </select>
      <label class="date">{{ t("Du") }} <input v-model="filters.from" type="date"></label>
      <label class="date">{{ t("au") }} <input v-model="filters.to" type="date"></label>
      <label class="fav"><input v-model="filters.fav" type="checkbox"><i class="fas fa-star"></i>{{ t("Favoris") }}</label>
      <button class="btn" type="button" @click="reset">{{ t("Effacer") }}</button>
    </form>
    <p class="small muted count">
      {{ total > items.length ? t("{n} résultats ({shown} affichés)", { n: total, shown: items.length }) : t("{n} résultats", { n: total }) }}
    </p>
  </section>

  <section class="card">
    <div v-if="loading && !items.length" class="grid-photos"><div v-for="i in 12" :key="i" class="skeleton cell"></div></div>
    <p v-else-if="!items.length" class="muted">{{ filters.fav ? t("Aucune photo favorite pour l'instant : touchez l'étoile d'une photo pour l'ajouter.") : t("Aucune photo ne correspond.") }}</p>
    <div v-else class="grid-photos">
      <figure v-for="(item, index) in items" :key="item.path" class="cell">
        <button type="button" class="open" @click="open = index"><img :src="item.thumb" alt="" loading="lazy"></button>
        <i v-if="item.video" class="fas fa-play-circle badge-video"></i>
        <button type="button" class="star" :class="{ on: item.favorite }" :title="t('Favori')" @click="toggleFavorite(item)">
          <i :class="item.favorite ? 'fas fa-star' : 'far fa-star'"></i></button>
      </figure>
    </div>
  </section>

  <div v-if="current" class="viewer" @click.self="open = null">
    <button class="nav prev" type="button" :title="t('Précédente')" @click="step(-1)"><i class="fas fa-chevron-left"></i></button>
    <div class="stage" @click.self="open = null">
      <video v-if="current.video" :key="current.url" :src="current.url" controls autoplay></video>
      <img v-else :key="current.url" :src="current.url" alt="">
      <div class="info">
        <div class="spacer">
          <strong v-if="current.date">{{ dateLabel(current.date) }}</strong>
          <span v-if="current.place"> · {{ current.place }}</span>
          <p v-if="current.people.length" class="small">{{ current.people.join(", ") }}</p>
          <form class="caption" @submit.prevent="saveCaption(current)">
            <input v-model="captionText" type="text" maxlength="300" :placeholder="t('Ajouter une légende…')">
            <button class="btn" type="submit" :disabled="captionText === (current.caption || '')"><i class="fas fa-check"></i></button>
            <button class="btn" type="button" :title="t('Style de cette légende')" @click="styling = true"><i class="fas fa-palette"></i></button>
          </form>
          <p v-if="current.suggestion && (current.suggestion.caption || current.suggestion.tags?.length)" class="small suggestion">
            <i class="fas fa-magic"></i>
            <span v-if="current.suggestion.caption">{{ current.suggestion.caption }}</span>
            <span v-if="current.suggestion.tags?.length" class="dim"> · {{ current.suggestion.tags.join(", ") }}</span>
            <button v-if="current.suggestion.caption && current.suggestion.caption !== captionText" class="btn small" type="button"
                    @click="captionText = current.suggestion.caption || ''">{{ t("Utiliser comme légende") }}</button>
          </p>
          <PhotoComments :path="current.path" />
          <VoiceMemo v-if="!current.video" :path="current.path" :seconds="current.voice" @changed="(s) => { if (current) current.voice = s; }" />
          <p class="small dim">{{ sourceLabel(current.source) }} · {{ current.path.split("/").pop() }}</p>
        </div>
        <button v-if="!current.video" class="btn" type="button" :title="t('Coloriser cette photo noir et blanc')" @click="colorizePhoto(current)">
          <i class="fas fa-palette"></i>{{ t("Coloriser") }}</button>
        <button class="btn" type="button" @click="toggleFavorite(current)">
          <i :class="current.favorite ? 'fas fa-star' : 'far fa-star'"></i>{{ current.favorite ? t("Favori") : t("Ajouter aux favoris") }}</button>
        <button class="btn icon" type="button" :title="t('Fermer')" @click="open = null"><i class="fas fa-times"></i></button>
      </div>
    </div>
    <button class="nav next" type="button" :title="t('Suivante')" @click="step(1)"><i class="fas fa-chevron-right"></i></button>
  </div>
  <CaptionEditor v-if="styling && current" scope="photo" :photo="current.path" :text="captionText" @close="styling = false" />
  <PhotoBookCard v-if="!props.favorites" />
</template>

<style scoped>
.filters { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.search { flex: 1 1 260px; display: flex; align-items: center; gap: .5rem; border: 1px solid var(--border); border-radius: 10px; padding: 0 .7rem; background: var(--surface); }
.search i { color: var(--muted); }
.smart { display: flex; align-items: center; gap: .35rem; font-size: .85rem; white-space: nowrap; }
.search input { border: 0; flex: 1; padding: .5rem 0; outline: none; }
.date { display: flex; align-items: center; gap: .3rem; font-size: .9rem; color: var(--muted); }
.date input { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .35rem .5rem; }
.fav { display: flex; align-items: center; gap: .35rem; font-weight: 600; }
.fav i { color: #e0a100; }
.count { margin-top: .7rem; }
.grid-photos { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: .45rem; }
.cell { margin: 0; position: relative; aspect-ratio: 1; border-radius: 10px; overflow: hidden; background: var(--surface-2); }
.open { border: 0; padding: 0; width: 100%; height: 100%; cursor: zoom-in; background: none; }
.open img { width: 100%; height: 100%; object-fit: cover; }
.badge-video { position: absolute; left: 6px; bottom: 6px; color: #fff; text-shadow: 0 1px 4px rgba(0, 0, 0, .6); pointer-events: none; }
.star { position: absolute; top: 4px; right: 4px; border: 0; background: rgba(0, 0, 0, .35); color: #fff; width: 30px; height: 30px; border-radius: 50%; cursor: pointer; opacity: 0; transition: opacity .15s; }
.cell:hover .star, .star.on { opacity: 1; }
.star.on { color: #ffc93c; }
@media (hover: none) { .star { opacity: 1; } }
.viewer { position: fixed; inset: 0; z-index: 60; background: rgba(8, 9, 12, .94); display: flex; align-items: center; color: #fff; }
.stage { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 1rem; gap: .8rem; min-width: 0; }
.stage img, .stage video { max-width: 100%; max-height: calc(100vh - 9rem); border-radius: 8px; object-fit: contain; }
.info { display: flex; gap: .6rem; align-items: center; width: min(900px, 100%); }
.info .btn { background: rgba(255, 255, 255, .1); color: #fff; border-color: rgba(255, 255, 255, .2); }
.dim { opacity: .6; }
.caption { display: flex; gap: .4rem; margin: .4rem 0; }
.suggestion { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; margin: .3rem 0; }
.suggestion .dim { opacity: .7; }
.caption input { flex: 1; min-width: 0; font: inherit; color: #fff; background: rgba(255, 255, 255, .1); border: 1px solid rgba(255, 255, 255, .25); border-radius: 10px; padding: .4rem .6rem; }
.nav { border: 0; background: rgba(255, 255, 255, .08); color: #fff; width: 3rem; height: 3rem; border-radius: 50%; margin: 0 .5rem; cursor: pointer; flex: none; }
@media (max-width: 760px) { .nav { position: absolute; bottom: 1rem; z-index: 2; } .prev { left: 1rem; } .next { right: 1rem; } .info { flex-wrap: wrap; padding-bottom: 3.5rem; } }
</style>
