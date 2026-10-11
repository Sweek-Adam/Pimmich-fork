<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ApiError, get, post } from "../api";
import { currentLang, t } from "../i18n";
import { run } from "../toast";

interface Tide { high: boolean; iso: string; meters: number }
interface TideInfo { tides: Tide[]; updated: string; cooldown: boolean }
const info = ref<TideInfo | null>(null);
const message = ref("");
const busy = ref(false);

async function load() {
  try { info.value = await get<TideInfo>("/api/tide_info"); message.value = ""; }
  catch (e) { info.value = null; message.value = (e as ApiError).message; }
}

async function action(url: string) {
  busy.value = true;
  await run(() => post(url));
  busy.value = false;
  load();
}

const when = (iso: string) => new Date(iso).toLocaleString(currentLang(), { weekday: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });

onMounted(load);
</script>

<template>
  <section class="card tides">
    <div class="card-head"><h2><i class="fas fa-water"></i>{{ t("Prochaines marées") }}</h2></div>
    <ul v-if="info?.tides.length" class="list">
      <li v-for="tide in info.tides" :key="tide.iso">
        <i class="fas" :class="tide.high ? 'fa-arrow-up high' : 'fa-arrow-down low'"></i>
        <strong>{{ tide.high ? t("Pleine mer") : t("Basse mer") }}</strong>
        <span class="spacer">{{ when(tide.iso) }}</span>
        <span class="muted small">{{ tide.meters.toLocaleString(currentLang()) }} m</span>
      </li>
    </ul>
    <p v-else-if="info" class="small muted">{{ t("Aucune donnée de marée à afficher.") }}</p>
    <p v-if="message" class="small muted">{{ message }}</p>
    <p v-if="info?.cooldown" class="small warn">{{ t("Quota StormGlass atteint : nouvel essai dans 12 heures.") }}</p>
    <p v-if="info?.updated" class="small muted">{{ t("Dernière mise à jour :") }} {{ new Date(info.updated).toLocaleString(currentLang()) }}</p>
    <div class="row">
      <button class="btn" type="button" :disabled="busy" @click="action('/test-stormglass-api')"><i class="fas fa-plug"></i>{{ t("Tester la connexion") }}</button>
      <button class="btn" type="button" :disabled="busy" @click="action('/api/force_tide_update')"><i class="fas fa-sync-alt"></i>{{ t("Forcer la mise à jour") }}</button>
    </div>
    <p class="small muted">{{ t("La version gratuite de StormGlass limite le nombre d'appels par jour : le cadre ne les récupère que deux fois par jour.") }}</p>
  </section>
</template>

<style scoped>
.tides { margin-top: 1rem; }
.list { list-style: none; padding: 0; margin: .3rem 0; }
.list li { display: flex; align-items: center; gap: .6rem; padding: .45rem 0; border-bottom: 1px solid var(--border); }
.high { color: var(--accent); } .low { color: var(--muted); }
.warn { color: var(--warn); }
</style>
