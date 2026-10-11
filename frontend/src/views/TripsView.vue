<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef } from "vue";
import { get, post } from "../api";
import { boot } from "../boot";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface Country { iso: string; name: string }
interface Trip {
  id: string; kind: "trip" | "outing" | "unplaced"; title: string; dates: string; start: string; count: number;
  lat: number | null; lon: number | null; route: [number, number][]; countries: Country[]; manual: boolean;
  distance_km: number | null; cover_url: string;
}
interface TripsData {
  home: [number, number] | null; trips: Trip[]; visited: string[];
  years: Record<string, { trips: number; countries: string[] }>;
  memories: { id: string; years: number }[];
  settings: { cards: string; osm_tiles: boolean; search: boolean };
}
interface Place { name: string; lat: number; lon: number; bbox?: number[] }

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Leaflet = any;
declare global { interface Window { L?: Leaflet } }

const data = ref<TripsData | null>(null);
const year = ref<string | null>(null);
const selected = ref<Trip | null>(null);
const photos = ref<{ path: string; thumb: string }[]>([]);
const placing = ref<{ id?: string; home?: boolean; title: string; name: string } | null>(null);
const query = ref("");
const results = ref<Place[] | null>(null);
const mapEl = ref<HTMLElement | null>(null);
const map = shallowRef<Leaflet>(null);
let layers: Leaflet = null;

const trips = computed(() => (data.value?.trips ?? []).filter((t) => !year.value || t.start.startsWith(year.value)));
const years = computed(() => [...new Set((data.value?.trips ?? []).map((t) => t.start.slice(0, 4)))].sort().reverse());
const totals = computed(() => {
  const all = data.value?.trips ?? [];
  return {
    trips: all.filter((t) => t.kind === "trip").length,
    outings: all.filter((t) => t.kind === "outing").length,
    countries: data.value?.visited.length ?? 0,
    unplaced: all.filter((t) => t.kind === "unplaced").length,
  };
});
const memory = computed(() => {
  const m = data.value?.memories[0];
  const trip = m && data.value?.trips.find((t) => t.id === m.id);
  return m && trip ? { trip, text: m.years === 1 ? t("Il y a un an : {title}", { title: trip.title }) : t("Il y a {n} ans : {title}", { n: m.years, title: trip.title }) } : null;
});
const grouped = computed(() => {
  const out: { year: string; items: Trip[] }[] = [];
  for (const trip of trips.value) {
    const y = trip.start.slice(0, 4);
    if (!out.length || out[out.length - 1].year !== y) out.push({ year: y, items: [] });
    out[out.length - 1].items.push(trip);
  }
  return out;
});
const kindLabel = (kind: Trip["kind"]) => ({ trip: t("Voyage"), outing: t("Sortie"), unplaced: t("À placer") })[kind];

function loadLeaflet(): Promise<void> {
  if (window.L) return Promise.resolve();
  return new Promise((resolve) => {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "/static/vendor/leaflet/leaflet.min.css";
    document.head.append(css);
    const js = document.createElement("script");
    js.src = "/static/vendor/leaflet/leaflet.min.js";
    js.onload = () => resolve();
    document.head.append(js);
  });
}

async function load() {
  data.value = await get<TripsData>("/api/trips");
}

async function initMap() {
  await loadLeaflet();
  const L = window.L;
  map.value = L.map(mapEl.value, { worldCopyJump: true, minZoom: 1 }).setView([30, 10], 2);
  if (data.value?.settings.osm_tiles) {
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(map.value);
  } else {
    const world = await get("/api/map/world.json");
    const visited = new Set(data.value?.visited);
    L.geoJSON(world, {
      style: (f: { properties: { iso: string } }) => ({
        color: "#c4baaa", weight: 1, fillOpacity: 1, fillColor: visited.has(f.properties.iso) ? "#f7cda0" : "#f6f2e9",
      }),
    }).addTo(map.value);
  }
  layers = L.layerGroup().addTo(map.value);
  map.value.on("click", (e: { latlng: { lat: number; lng: number } }) => { if (placing.value) placeAt(e.latlng.lat, e.latlng.lng, ""); });
  drawMap(true);
}

function drawMap(fit = false) {
  const L = window.L;
  if (!map.value || !L) return;
  layers.clearLayers();
  const bounds: [number, number][] = [];
  if (data.value?.home) {
    L.marker(data.value.home, { icon: L.divIcon({ className: "home-pin", iconSize: [16, 16] }), title: t("Maison") }).addTo(layers);
  }
  for (const trip of trips.value) {
    if (trip.lat === null || trip.lon === null) continue;
    const color = trip.kind === "trip" ? "#d64c34" : "#2f8f5b";
    if (trip.route.length > 1) L.polyline(trip.route, { color, weight: 2, dashArray: "6 6", opacity: 0.8 }).addTo(layers);
    const marker = L.circleMarker([trip.lat, trip.lon], {
      radius: Math.min(18, 6 + Math.sqrt(trip.count)), color: "#fff", weight: 2, fillColor: color,
      fillOpacity: selected.value?.id === trip.id ? 1 : 0.85,
    }).addTo(layers);
    marker.bindTooltip(`${trip.title} · ${trip.dates}`);
    marker.on("click", (ev: unknown) => { L.DomEvent.stopPropagation(ev); select(trip, false); });
    bounds.push([trip.lat, trip.lon]);
  }
  if (fit && bounds.length) map.value.fitBounds(bounds, { padding: [40, 40], maxZoom: 7 });
}

async function select(trip: Trip, zoom = true) {
  selected.value = trip;
  photos.value = [];
  drawMap();
  if (zoom && trip.lat !== null && map.value) {
    if (trip.route.length > 1) map.value.fitBounds(trip.route, { padding: [60, 60], maxZoom: 9 });
    else map.value.setView([trip.lat, trip.lon], 8);
  }
  try {
    const d = await get<{ photos: { path: string; thumb: string }[] }>(`/api/trips/${encodeURIComponent(trip.id)}`);
    photos.value = d.photos.slice(0, 120);
  } catch (e) {
    notify((e as Error).message, true);
  }
  await nextTick();
  document.getElementById("trip-detail")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function reload() {
  const id = selected.value?.id;
  const start = selected.value?.start;
  await load();
  drawMap();
  const again = data.value?.trips.find((t) => t.id === id) || data.value?.trips.find((t) => t.start === start);
  if (again) select(again, false);
}

function startPlacing(trip?: Trip, name = "") {
  placing.value = trip ? { id: trip.id, title: name || trip.title, name } : { home: true, title: "", name: "" };
  query.value = name;
  results.value = null;
  mapEl.value?.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function placeAt(lat: number, lon: number, suggested: string) {
  const target = placing.value;
  if (!target) return;
  placing.value = null;
  if (target.home) {
    await run(() => post("/api/trips/home", { lat, lon }));
  } else {
    const name = target.name || suggested || window.prompt(t("Nom de cet endroit (facultatif) :"), "") || "";
    await run(() => post(`/api/trips/${encodeURIComponent(target.id!)}/place`, { lat, lon, name }));
  }
  await reload();
}

async function search() {
  if (query.value.trim().length < 2) return;
  const d = await get<{ results: Place[] }>(`/api/places/search?q=${encodeURIComponent(query.value.trim())}`);
  results.value = d.results;
}

function choose(place: Place) {
  map.value?.setView([place.lat, place.lon], place.bbox ? 5 : 10);
  placeAt(place.lat, place.lon, place.name.split(",")[0]);
}

async function rename(trip: Trip) {
  const name = window.prompt(t("Nom de ce voyage :"), trip.title);
  if (name === null) return;
  if (trip.lat === null) return startPlacing(trip, name);
  await run(() => post(`/api/trips/${encodeURIComponent(trip.id)}/place`, { name }));
  await reload();
}

async function forget(trip: Trip) {
  await run(() => post(`/api/trips/${encodeURIComponent(trip.id)}/place`, {}, "DELETE"));
  await reload();
}

async function play(trip: Trip) {
  await run(() => post(`/api/trips/${encodeURIComponent(trip.id)}/play`));
}

async function saveSettings(change: { cards?: string; osm_tiles?: boolean }) {
  await run(() => post("/api/trips/settings", change));
  if ("osm_tiles" in change) window.location.reload();
}

function chooseYear(value: string | null) {
  year.value = value;
  drawMap(true);
}

onMounted(async () => {
  await load();
  await nextTick();
  initMap();
});
onUnmounted(() => map.value?.remove());
</script>

<template>
  <div v-if="!data" class="card"><div class="skeleton" style="height: 420px"></div></div>
  <template v-else>
    <section class="card">
      <div class="totals">
        <div><strong>{{ totals.trips }}</strong><span>{{ t("voyages") }}</span></div>
        <div><strong>{{ totals.outings }}</strong><span>{{ t("sorties") }}</span></div>
        <div><strong>{{ totals.countries }}</strong><span>{{ t("pays visités") }}</span></div>
        <div><strong>{{ totals.unplaced }}</strong><span>{{ t("moments à placer") }}</span></div>
      </div>
      <button v-if="memory" type="button" class="banner memory" @click="select(memory.trip)"><i class="fas fa-history"></i>{{ memory.text }}</button>
      <div v-if="!data.home && boot.admin" class="banner">
        <i class="fas fa-home"></i><span class="spacer">{{ t("Où est la maison ? Placez-la pour distinguer les voyages des sorties.") }}</span>
        <button class="btn" type="button" @click="startPlacing()">{{ t("Placer la maison") }}</button>
      </div>
      <div class="row years">
        <button type="button" class="chip" :class="{ active: !year }" @click="chooseYear(null)">{{ t("Toutes les années") }}</button>
        <button v-for="y in years" :key="y" type="button" class="chip" :class="{ active: year === y }" @click="chooseYear(y)">{{ y }}</button>
        <span class="spacer"></span>
        <button v-if="data.home && boot.admin" class="btn small" type="button" @click="startPlacing()"><i class="fas fa-home"></i>{{ t("Placer la maison") }}</button>
      </div>
      <div v-if="placing" class="placing">
        <p><i class="fas fa-map-pin"></i>
          {{ placing.home ? t("Cliquez sur la carte à l'endroit de la maison, ou cherchez votre ville.") : t("Cliquez sur la carte à l'endroit de « {title} », ou cherchez un lieu.", { title: placing.title }) }}</p>
        <form class="row" @submit.prevent="search">
          <input v-model="query" type="search" class="spacer" :placeholder="t('Chercher un lieu (ville, pays)…')">
          <button class="btn primary icon" type="submit"><i class="fas fa-search"></i></button>
          <button class="btn" type="button" @click="placing = null">{{ t("Annuler") }}</button>
        </form>
        <p v-if="results && !results.length" class="small">{{ t("Aucun lieu trouvé.") }}</p>
        <button v-for="place in results || []" :key="place.name + place.lat" type="button" class="result" @click="choose(place)">{{ place.name }}</button>
      </div>
      <div ref="mapEl" class="map" :class="{ crosshair: placing }"></div>
    </section>

    <section v-if="selected" id="trip-detail" class="card">
      <div class="card-head">
        <div>
          <h2>{{ selected.title }}</h2>
          <p class="small muted">
            {{ selected.dates }} · {{ t("{n} photos", { n: selected.count }) }}
            <template v-if="selected.countries.length"> · {{ selected.countries.map((c) => c.name).join(", ") }}</template>
            <template v-if="selected.distance_km !== null && selected.kind !== 'unplaced'"> · {{ t("à {n} km de la maison", { n: selected.distance_km }) }}</template>
          </p>
        </div>
        <button class="btn icon" type="button" :title="t('Fermer')" @click="selected = null"><i class="fas fa-times"></i></button>
      </div>
      <div class="row">
        <button class="btn primary" type="button" @click="play(selected)"><i class="fas fa-play"></i>{{ t("Raconter sur le cadre") }}</button>
        <button class="btn" type="button" @click="startPlacing(selected)"><i class="fas fa-map-marker-alt"></i>{{ selected.lat === null ? t("Placer sur la carte") : t("Déplacer") }}</button>
        <button class="btn" type="button" @click="rename(selected)"><i class="fas fa-pen"></i>{{ t("Renommer") }}</button>
        <button v-if="selected.manual" class="btn danger" type="button" @click="forget(selected)"><i class="fas fa-undo"></i>{{ t("Oublier la position donnée") }}</button>
      </div>
      <img v-if="selected.lat !== null" :key="selected.id + selected.title" :src="`/api/trips/${encodeURIComponent(selected.id)}/card.jpg?t=${selected.title}`" class="trip-card" alt="">
      <div class="thumbs" style="margin-top: .9rem">
        <img v-for="p in photos" :key="p.path" :src="p.thumb" alt="" loading="lazy">
      </div>
    </section>

    <section class="card">
      <div class="card-head"><h2><i class="fas fa-stream"></i>{{ t("Chronologie") }}</h2></div>
      <p v-if="!trips.length" class="muted">{{ t("Aucune photo datée pour l'instant : les voyages apparaîtront avec les photos.") }}</p>
      <div v-for="group in grouped" :key="group.year">
        <h3 class="year">{{ group.year }}
          <small v-if="data.years[group.year]" class="muted">{{ data.years[group.year].trips }} ✈ · {{ data.years[group.year].countries.join(", ") }}</small>
        </h3>
        <button v-for="trip in group.items" :key="trip.id" type="button" class="item" :class="{ active: selected?.id === trip.id }" @click="select(trip)">
          <img :src="trip.cover_url" alt="" loading="lazy">
          <span class="spacer">
            <strong>{{ trip.title }}</strong>
            <span class="small muted"><span class="kind" :class="trip.kind">{{ kindLabel(trip.kind) }}</span> {{ trip.dates }} · {{ t("{n} photos", { n: trip.count }) }}</span>
          </span>
          <i class="fas fa-chevron-right muted"></i>
        </button>
      </div>
    </section>

    <section v-if="boot.admin" class="card">
      <div class="card-head"><h2><i class="fas fa-sliders-h"></i>{{ t("Sur le cadre") }}</h2></div>
      <label class="field">
        <span>{{ t("Cartes dans le diaporama") }}</span>
        <select :value="data.settings.cards" @change="saveSettings({ cards: ($event.target as HTMLSelectElement).value })">
          <option value="off">{{ t("Aucune") }}</option>
          <option value="memories">{{ t("Souvenirs du jour (« il y a un an, nous étions… »)") }}</option>
          <option value="all">{{ t("Tous les voyages, les souvenirs et le récapitulatif de chaque année") }}</option>
        </select>
      </label>
      <label class="check">
        <input type="checkbox" :checked="data.settings.osm_tiles" @change="saveSettings({ osm_tiles: ($event.target as HTMLInputElement).checked })">
        <span>{{ t("Fond de carte détaillé OpenStreetMap dans cette page (les images de la carte viennent d'openstreetmap.org)") }}</span>
      </label>
      <p class="small muted">{{ t("La recherche de villes utilise OpenStreetMap quand « Trouver le nom du lieu » est activé dans Infos des photos ; sinon, seuls les pays sont proposés, et vous pouvez toujours cliquer sur la carte.") }}</p>
    </section>
  </template>
</template>

<style scoped>
.totals { display: grid; grid-template-columns: repeat(4, 1fr); gap: .6rem; }
.totals div { background: var(--surface-2); border-radius: 12px; padding: .6rem; text-align: center; }
.totals strong { display: block; font-size: 1.45rem; }
.totals span { color: var(--muted); font-size: .82rem; }
@media (max-width: 640px) { .totals { grid-template-columns: repeat(2, 1fr); } }
.banner { display: flex; gap: .6rem; align-items: center; width: 100%; margin-top: .8rem; padding: .7rem .9rem; border-radius: 12px; border: 0; font: inherit; text-align: left; background: var(--warn-soft); color: var(--text); }
.banner.memory { cursor: pointer; font-weight: 600; }
.banner i { color: var(--warn); }
.years { margin-top: .8rem; }
.chip { border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: 999px; padding: .2rem .8rem; font: inherit; font-size: .85rem; cursor: pointer; }
.chip.active { background: #d64c34; border-color: #d64c34; color: #fff; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.placing { margin-top: .8rem; padding: .8rem; border-radius: 12px; background: var(--accent-soft); display: grid; gap: .5rem; }
.placing i { color: var(--accent); margin-right: .4rem; }
.result { text-align: left; border: 0; background: var(--surface); color: var(--text); font: inherit; padding: .4rem .6rem; border-radius: 8px; cursor: pointer; }
.result:hover { background: var(--surface-2); }
.map { height: 60vh; min-height: 320px; border-radius: 12px; margin-top: .8rem; background: #cde1ec; z-index: 0; }
.map.crosshair { cursor: crosshair; }
:deep(.home-pin) { background: #3478be; border: 3px solid #fff; border-radius: 50%; box-shadow: 0 1px 4px rgba(0, 0, 0, .4); }
:deep(.leaflet-container) { font: inherit; }
.trip-card { width: 100%; max-width: 720px; border-radius: 12px; margin-top: .9rem; }
.year { margin: 1rem 0 .4rem; font-size: 1.05rem; }
.year small { font-weight: 400; margin-left: .4rem; }
.item { display: flex; gap: .8rem; align-items: center; width: 100%; padding: .5rem; border: 0; border-radius: 12px; background: none; font: inherit; color: var(--text); text-align: left; cursor: pointer; }
.item:hover, .item.active { background: var(--surface-2); }
.item img { width: 78px; height: 54px; object-fit: cover; border-radius: 8px; background: var(--surface-2); flex: none; }
.item .spacer { display: grid; }
.kind { font-size: .7rem; padding: 1px 7px; border-radius: 999px; color: #fff; }
.kind.trip { background: #d64c34; } .kind.outing { background: #2f8f5b; } .kind.unplaced { background: #888; }
.field { display: grid; gap: .3rem; font-weight: 600; }
.field select { font-weight: 400; max-width: 100%; }
.check { display: flex; gap: .6rem; align-items: flex-start; margin: .9rem 0 .4rem; }
</style>
