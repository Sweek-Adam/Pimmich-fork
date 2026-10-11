<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { boot, classicUrl } from "../boot";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface Playlist { id: string; name: string; photos: string[]; owner?: string; music_file?: string | null }
interface LibraryItem { path: string; thumb: string; source: string; date: string | null; video: boolean; favorite: boolean }

const playlists = ref<Playlist[] | null>(null);
const mineOnly = ref(false);
const library = ref<LibraryItem[]>([]);
const thumbs = computed(() => new Map(library.value.map((i) => [i.path, i.thumb])));
const editor = reactive({ open: false, id: "" as string, name: "", selected: [] as string[], source: "", year: "", fav: false });

const shown = computed(() => (playlists.value ?? []).filter((p) => !mineOnly.value || p.owner === boot.user));
const sources = computed(() => [...new Set(library.value.map((i) => i.source))].sort());
const years = computed(() => [...new Set(library.value.map((i) => (i.date || "").slice(0, 4)).filter(Boolean))].sort().reverse());
const candidates = computed(() => library.value.filter((i) =>
  (!editor.source || i.source === editor.source) && (!editor.year || (i.date || "").startsWith(editor.year)) && (!editor.fav || i.favorite)));
const selectedSet = computed(() => new Set(editor.selected));

const thumbOf = (path: string) => thumbs.value.get(path) || `/static/prepared/${path}`;

async function load() {
  playlists.value = await get<Playlist[]>("/api/playlists");
}

async function loadLibrary() {
  if (!library.value.length) library.value = (await get<{ items: LibraryItem[] }>("/api/library")).items;
}

async function play(p: Playlist) {
  await run(() => post("/api/playlists/play", { id: p.id }));
  document.dispatchEvent(new Event("pimmich:status"));
}

async function backToStandard() {
  await run(() => post("/api/slideshow/restart_standard"));
}

async function rename(p: Playlist) {
  const name = window.prompt(t("Nouveau nom de la playlist :"), p.name);
  if (!name || name.trim() === p.name) return;
  await run(() => post(`/api/playlists/${p.id}/rename`, { name: name.trim() }));
  load();
}

async function remove(p: Playlist) {
  if (!window.confirm(t("Supprimer la playlist « {name} » ?", { name: p.name }))) return;
  await run(() => post(`/api/playlists/${p.id}`, {}, "DELETE"), t("Playlist supprimée."));
  load();
}

async function openEditor(p?: Playlist) {
  Object.assign(editor, { open: true, id: p?.id ?? "", name: p?.name ?? "", selected: [...(p?.photos ?? [])], source: "", year: "", fav: false });
  try {
    await loadLibrary();
  } catch (e) {
    notify((e as Error).message, true);
  }
}

function toggle(path: string) {
  editor.selected = selectedSet.value.has(path) ? editor.selected.filter((p) => p !== path) : [...editor.selected, path];
}

function selectAll() {
  const add = candidates.value.map((i) => i.path).filter((p) => !selectedSet.value.has(p));
  editor.selected = [...editor.selected, ...add];
}

function unselectShown() {
  const hide = new Set(candidates.value.map((i) => i.path));
  editor.selected = editor.selected.filter((p) => !hide.has(p));
}

async function save() {
  if (!editor.selected.length) return notify(t("Choisissez au moins une photo."), true);
  if (editor.id) {
    const done = await run(() => post(`/api/playlists/${editor.id}/photos`, { photos: editor.selected }, "PUT"), t("Playlist enregistrée."));
    if (!done) return;
  } else {
    if (!editor.name.trim()) return notify(t("Donnez un nom à la playlist."), true);
    const done = await run(() => post("/api/playlists", { name: editor.name.trim(), photos: editor.selected }), t("Playlist créée."));
    if (!done) return;
  }
  editor.open = false;
  load();
}

onMounted(load);
</script>

<template>
  <section class="card">
    <div class="card-head">
      <h2><i class="fas fa-list-ul"></i>{{ t("Vos Playlists") }}</h2>
      <div class="row">
        <button class="btn" type="button" @click="backToStandard"><i class="fas fa-stop-circle"></i>{{ t("Retour au diaporama standard") }}</button>
        <button class="btn primary" type="button" @click="openEditor()"><i class="fas fa-plus"></i>{{ t("Nouvelle playlist") }}</button>
      </div>
    </div>
    <p class="small muted">{{ t("Choisissez les photos d'un coup, par source, année, mois ou favoris.") }}
      <a :href="classicUrl('tab-playlists')">{{ t("Albums intelligents, musique et disposition : interface classique") }}</a></p>
    <label class="check"><input v-model="mineOnly" type="checkbox">{{ t("Seulement mes playlists") }}</label>
    <div v-if="!playlists" class="skeleton" style="height: 140px"></div>
    <p v-else-if="!shown.length" class="muted">{{ t("Aucune playlist pour l'instant.") }}</p>
    <div v-else class="playlists">
      <article v-for="p in shown" :key="p.id" class="playlist">
        <div class="mosaic">
          <img v-for="path in p.photos.slice(0, 4)" :key="path" :src="thumbOf(path)" alt="" loading="lazy">
          <span v-if="!p.photos.length" class="empty"><i class="fas fa-images"></i></span>
        </div>
        <div class="body">
          <strong>{{ p.name }}</strong>
          <span class="small muted">{{ t("{n} photos", { n: p.photos.length }) }}<template v-if="p.owner"> · {{ p.owner }}</template></span>
          <div class="row actions">
            <button class="btn primary" type="button" :disabled="!p.photos.length" @click="play(p)"><i class="fas fa-play"></i>{{ t("Lancer") }}</button>
            <button class="btn icon" type="button" :title="t('Modifier les photos')" @click="openEditor(p)"><i class="fas fa-images"></i></button>
            <button class="btn icon" type="button" :title="t('Renommer')" @click="rename(p)"><i class="fas fa-pen"></i></button>
            <button class="btn icon danger" type="button" :title="t('Supprimer')" @click="remove(p)"><i class="fas fa-trash-alt"></i></button>
          </div>
        </div>
      </article>
    </div>
  </section>

  <div v-if="editor.open" class="editor-backdrop" @click.self="editor.open = false">
    <div class="editor">
      <div class="card-head">
        <h2>{{ editor.id ? editor.name : t("Nouvelle playlist") }}</h2>
        <button class="btn icon" type="button" :title="t('Fermer')" @click="editor.open = false"><i class="fas fa-times"></i></button>
      </div>
      <div class="row filters">
        <input v-if="!editor.id" v-model="editor.name" type="text" :placeholder="t('Nom de la playlist')" class="name">
        <select v-model="editor.source"><option value="">{{ t("Toutes les sources") }}</option><option v-for="s in sources" :key="s" :value="s">{{ s }}</option></select>
        <select v-model="editor.year"><option value="">{{ t("Toutes les années") }}</option><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select>
        <label class="check"><input v-model="editor.fav" type="checkbox">{{ t("Favoris") }}</label>
        <span class="spacer"></span>
        <button class="btn" type="button" @click="selectAll">{{ t("Tout sélectionner") }}</button>
        <button class="btn" type="button" @click="unselectShown">{{ t("Tout désélectionner") }}</button>
      </div>
      <div class="picker">
        <div v-if="!library.length" class="skeleton" style="height: 200px"></div>
        <button v-for="item in candidates" :key="item.path" type="button" class="pick" :class="{ on: selectedSet.has(item.path) }" @click="toggle(item.path)">
          <img :src="item.thumb" alt="" loading="lazy">
          <span v-if="selectedSet.has(item.path)" class="order">{{ editor.selected.indexOf(item.path) + 1 }}</span>
          <i v-if="item.video" class="fas fa-video video"></i>
        </button>
      </div>
      <div class="row footer">
        <span class="muted">{{ t("{n} photos sélectionnées", { n: editor.selected.length }) }}</span>
        <span class="spacer"></span>
        <button class="btn" type="button" @click="editor.open = false">{{ t("Annuler") }}</button>
        <button class="btn primary" type="button" @click="save"><i class="fas fa-check"></i>{{ t("Enregistrer") }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.check { display: flex; align-items: center; gap: .5rem; margin: .7rem 0; }
.playlists { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .9rem; }
.playlist { border: 1px solid var(--border); border-radius: 14px; overflow: hidden; background: var(--surface); }
.mosaic { display: grid; grid-template-columns: 1fr 1fr; aspect-ratio: 16 / 9; background: var(--surface-2); }
.mosaic img { width: 100%; height: 100%; object-fit: cover; }
.mosaic img:only-child { grid-column: 1 / -1; grid-row: 1 / 3; }
.empty { grid-column: 1 / -1; grid-row: 1 / 3; display: grid; place-items: center; color: var(--muted); font-size: 1.6rem; }
.body { padding: .7rem .8rem .8rem; display: grid; gap: .2rem; }
.actions { margin-top: .4rem; }
.actions .btn.icon { width: 2.3rem; height: 2.3rem; }
.editor-backdrop { position: fixed; inset: 0; z-index: 55; background: rgba(0, 0, 0, .45); display: grid; place-items: center; padding: 1rem; }
.editor { width: min(1100px, 100%); max-height: 100%; display: flex; flex-direction: column; background: var(--surface); border-radius: 18px; padding: 1rem; box-shadow: var(--shadow); }
.filters { margin-bottom: .7rem; }
.filters .name { flex: 1 1 200px; }
.picker { flex: 1; overflow-y: auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: .4rem; min-height: 200px; }
.pick { position: relative; aspect-ratio: 1; border: 3px solid transparent; border-radius: 10px; padding: 0; overflow: hidden; cursor: pointer; background: var(--surface-2); }
.pick img { width: 100%; height: 100%; object-fit: cover; }
.pick.on { border-color: var(--accent); }
.pick.on img { opacity: .85; }
.order { position: absolute; top: 4px; left: 4px; background: var(--accent); color: var(--accent-text); font-size: .72rem; font-weight: 700; border-radius: 999px; padding: 0 .45rem; }
.video { position: absolute; right: 6px; bottom: 6px; color: #fff; text-shadow: 0 1px 4px rgba(0, 0, 0, .6); }
.footer { margin-top: .8rem; }
@media (max-width: 760px) { .editor-backdrop { padding: 0; } .editor { border-radius: 0; height: 100%; } }
</style>
