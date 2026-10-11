<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { get, post } from "../../api";
import { t } from "../../i18n";
import { run } from "../../toast";

const data = ref<{ settings: Record<string, boolean>; excluded: { path: string; thumb: string; reasons: string[] }[] } | null>(null);
const open = ref(false);
const switches = computed(() => [
  ["filter_blurry", t("Photos floues")], ["filter_dark", t("Photos très sombres")], ["filter_screenshots", t("Captures d'écran")],
  ["filter_bursts", t("Rafales : seule la plus nette est gardée")]]);
const reasons = computed<Record<string, string>>(() => ({ blurry: t("floue"), dark: t("très sombre"), screenshot: t("capture d'écran"), burst: t("rafale") }));
async function load() { data.value = await get("/api/quality"); }
async function set(key: string, value: boolean) { await run(() => post("/api/quality", { [key]: value })); load(); }
async function keep(path: string) { await run(() => post("/api/quality/keep", { path })); load(); }
onMounted(() => load().catch(() => {}));
</script>

<template>
  <section v-if="data" class="card">
    <div class="card-head"><h2><i class="fas fa-magic"></i>{{ t("Tri automatique") }}</h2></div>
    <p class="small muted">{{ t("Écarte du diaporama les photos ratées. Rien n'est supprimé : vous pouvez remettre chaque photo d'un clic.") }}</p>
    <label class="check strong"><input type="checkbox" class="switch" :checked="data.settings.auto_filter_enabled" @change="set('auto_filter_enabled', ($event.target as HTMLInputElement).checked)">{{ t("Activer le tri automatique") }}</label>
    <div v-if="data.settings.auto_filter_enabled" class="switches">
      <label v-for="[key, label] in switches" :key="key" class="check"><input type="checkbox" :checked="data.settings[key]" @change="set(key, ($event.target as HTMLInputElement).checked)">{{ label }}</label>
    </div>
    <button class="btn small" type="button" @click="open = !open"><i class="fas fa-eye"></i>{{ t("Voir les photos écartées") }} ({{ data.excluded.length }})</button>
    <div v-if="open" class="excluded">
      <p v-if="!data.excluded.length" class="small muted">{{ t("Aucune photo écartée.") }}</p>
      <figure v-for="item in data.excluded" :key="item.path"><img :src="item.thumb" alt="" loading="lazy">
        <figcaption>{{ item.reasons.map((r) => reasons[r] || r).join(", ") }}</figcaption>
        <button class="btn small" type="button" @click="keep(item.path)">{{ t("Remettre") }}</button></figure>
    </div>
  </section>
</template>

<style scoped>
.check { display: flex; align-items: center; gap: .6rem; margin: .5rem 0; }
.strong { font-weight: 600; }
.switches { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: .2rem; margin-bottom: .6rem; }
.excluded { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: .5rem; margin-top: .7rem; }
.excluded figure { margin: 0; display: grid; gap: .25rem; }
.excluded img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 8px; }
figcaption { font-size: .75rem; color: var(--muted); }
.btn.small { padding: .25rem .7rem; font-size: .8rem; width: fit-content; }
</style>
