<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Photomaton de fête : tirages 10 × 15 sur une imprimante Wi-Fi
interface Booth { enabled: boolean; uri: string; name: string; per_guest: number; auto: boolean; max_auto: number }
const booth = ref<Booth | null>(null);
const printers = ref<{ uri: string; name: string }[] | null>(null);
const searching = ref(false);

async function load() {
  try { booth.value = (await get<{ settings: Booth }>("/api/photobooth")).settings; } catch { booth.value = null; }
}
async function save(change: Partial<Booth>) {
  const r = await run(() => post<{ success: boolean; message?: string; settings: Booth }>("/api/photobooth", change, "PUT"));
  if (r?.settings) booth.value = r.settings;
}
async function search() {
  searching.value = true;
  try { printers.value = (await get<{ printers: { uri: string; name: string }[] }>("/api/photobooth/printers")).printers; } finally { searching.value = false; }
}
async function test() { await run(() => post("/api/photobooth/test")); }
onMounted(load);
</script>

<template>
  <section v-if="booth" class="card booth">
    <div class="card-head"><h2><i class="fas fa-print"></i>{{ t("Photomaton") }}</h2></div>
    <p class="small muted">{{ t("Pendant une fête, les invités impriment la photo affichée sur le cadre (tirage 10 × 15 avec le nom de la fête et la date) sur une imprimante Wi-Fi de la maison.") }}</p>
    <div class="row">
      <span class="small">{{ t("Imprimante :") }} <strong>{{ booth.name || booth.uri || t("aucune") }}</strong></span>
      <button class="btn small" type="button" :disabled="searching" @click="search">
        <i class="fas" :class="searching ? 'fa-spinner fa-spin' : 'fa-search'"></i> {{ t("Chercher les imprimantes") }}</button>
    </div>
    <div v-if="printers" class="row">
      <span v-if="!printers.length" class="small muted">{{ t("Aucune imprimante trouvée : allumez-la et vérifiez qu'elle est sur le même Wi-Fi.") }}</span>
      <button v-for="p in printers" :key="p.uri" class="btn small" :class="{ primary: p.uri === booth.uri }" type="button" @click="save({ uri: p.uri, name: p.name })">
        <i class="fas fa-print"></i> {{ p.name }}</button>
    </div>
    <template v-if="booth.uri">
      <label class="check"><input type="checkbox" :checked="booth.enabled" @change="save({ enabled: ($event.target as HTMLInputElement).checked })">
        {{ t("Ouvrir le photomaton pendant les fêtes") }}</label>
      <label class="small">{{ t("Tirages par invité") }}
        <input type="number" min="0" max="20" :value="booth.per_guest" class="num" @change="save({ per_guest: Number(($event.target as HTMLInputElement).value) })"></label>
      <label class="check"><input type="checkbox" :checked="booth.auto" @change="save({ auto: ($event.target as HTMLInputElement).checked })">
        {{ t("Imprimer aussi chaque photo reçue, au plus") }}
        <input type="number" min="1" max="500" :value="booth.max_auto" class="num" @change="save({ max_auto: Number(($event.target as HTMLInputElement).value) })"> {{ t("par fête") }}</label>
      <button class="btn small" type="button" @click="test"><i class="fas fa-print"></i> {{ t("Tirage d'essai") }}</button>
    </template>
  </section>
</template>

<style scoped>
.booth { margin-top: 1rem; display: grid; gap: .5rem; justify-items: start; }
.row { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
.check { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
.num { width: 4.5rem; margin: 0 .3rem; }
</style>
