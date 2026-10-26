<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Diffusion sur une télé Chromecast : le diaporama ou le film de l'année
interface CastState { available: boolean; running: boolean; state: { name: string | null; mode: string | null; shown: number; error: string | null }; films: string[] }
const state = ref<CastState | null>(null);
const devices = ref<{ uuid: string; name: string; model: string }[] | null>(null);
const device = ref("");
const film = ref("");
const searching = ref(false);
let timer: number | undefined;

async function load() {
  try {
    state.value = await get<CastState>("/api/chromecast");
    if (!film.value && state.value.films.length) film.value = state.value.films[state.value.films.length - 1];
  } catch { state.value = null; }
}
async function search() {
  searching.value = true;
  try {
    devices.value = (await get<{ devices: { uuid: string; name: string; model: string }[] }>("/api/chromecast/devices")).devices;
    if (!device.value && devices.value.length) device.value = devices.value[0].uuid;
  } catch (e) { devices.value = []; await run(() => Promise.reject(e)); } finally { searching.value = false; }
}
async function start(mode: "photos" | "film") {
  await run(() => post("/api/chromecast/start", { uuid: device.value, mode, film: film.value }));
  window.setTimeout(load, 3000);
}
async function stop() { await run(() => post("/api/chromecast/stop")); load(); }
onMounted(() => { load(); timer = window.setInterval(load, 5000); });
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section v-if="state" class="card cast">
    <div class="card-head"><h2><i class="fab fa-chromecast"></i>{{ t("Diffuser sur une télé") }}</h2></div>
    <p class="small muted">{{ t("Le diaporama ou le film de l'année sur une télé Chromecast ou Google TV de la maison, sans câble.") }}</p>
    <p v-if="!state.available" class="small warn">{{ t("Diffusion indisponible : lancez une fois ~/pimmich/venv/bin/pip install pychromecast") }}</p>
    <template v-else>
      <p v-if="state.running" class="small ok"><i class="fas fa-broadcast-tower"></i>
        {{ t("En cours sur « {name} » ({count} image(s) envoyée(s))", { name: state.state.name || "…", count: state.state.shown }) }}
        <button class="btn small danger" type="button" @click="stop"><i class="fas fa-stop"></i> {{ t("Arrêter") }}</button></p>
      <p v-else-if="state.state.error" class="small warn">{{ state.state.error }}</p>
      <div class="row">
        <button class="btn small" type="button" :disabled="searching" @click="search">
          <i class="fas" :class="searching ? 'fa-spinner fa-spin' : 'fa-search'"></i> {{ t("Chercher les télés") }}</button>
        <select v-if="devices && devices.length" v-model="device">
          <option v-for="d in devices" :key="d.uuid" :value="d.uuid">{{ d.name }}</option></select>
        <span v-else-if="devices" class="small muted">{{ t("Aucune télé trouvée sur le Wi-Fi.") }}</span>
      </div>
      <div v-if="device" class="row">
        <button class="btn small primary" type="button" @click="start('photos')"><i class="fas fa-images"></i> {{ t("Diffuser le diaporama") }}</button>
        <template v-if="state.films.length">
          <select v-model="film"><option v-for="f in state.films" :key="f" :value="f">{{ f.replace(/^film_|\.mp4$/g, "") }}</option></select>
          <button class="btn small" type="button" @click="start('film')"><i class="fas fa-film"></i> {{ t("Diffuser le film") }}</button>
        </template>
      </div>
    </template>
  </section>
</template>

<style scoped>
.cast { margin-top: 1rem; display: grid; gap: .5rem; }
.row { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
.ok { color: var(--ok); } .warn { color: var(--warn); }
</style>
