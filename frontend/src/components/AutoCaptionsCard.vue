<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Légendes proposées automatiquement : mots-clés d'Immich, ou descriptions écrites par Claude (photos envoyées à Anthropic)
interface State { enabled: boolean; mode: "immich" | "claude"; has_key: boolean; immich: boolean; done: number; described: number; running: boolean }
const state = ref<State | null>(null);
const apiKey = ref("");

async function load() { try { state.value = await get<State>("/api/auto_captions"); } catch { state.value = null; } }
async function save(change: Record<string, unknown>) {
  if (change.mode === "claude" && !window.confirm(t("Avec Claude, une copie réduite de chaque photo est envoyée à Anthropic pour être décrite (environ 0,7 centime par photo, facturé sur votre compte Anthropic). Continuer ?"))) return;
  await run(() => post("/api/auto_captions", change, "PUT"));
  apiKey.value = "";
  load();
}
async function runNow() { await run(() => post("/api/auto_captions/run")); window.setTimeout(load, 5000); }
onMounted(load);
</script>

<template>
  <section v-if="state" class="card auto">
    <div class="card-head"><h2><i class="fas fa-magic"></i>{{ t("Légendes proposées automatiquement") }}</h2></div>
    <p class="small muted">{{ t("Chaque nuit, le cadre propose pour les photos une courte description et des mots-clés (plage, neige, anniversaire…). Ils servent à la recherche de la bibliothèque, et chaque proposition peut devenir la légende en un clic. Une légende écrite à la main n'est jamais remplacée.") }}</p>
    <label class="check"><input type="checkbox" :checked="state.enabled" @change="save({ enabled: ($event.target as HTMLInputElement).checked })">
      {{ t("Proposer des légendes chaque nuit") }}</label>
    <div class="modes">
      <label class="check"><input type="radio" name="auto-mode" :checked="state.mode === 'immich'" @change="save({ mode: 'immich' })">
        <span><strong>Immich</strong> — {{ t("mots-clés seulement, gratuit, analysés par votre serveur Immich (photos importées d'Immich).") }}</span></label>
      <p v-if="state.mode === 'immich' && !state.immich" class="small warn">{{ t("Immich n'est pas configuré (Sources › Immich).") }}</p>
      <label class="check"><input type="radio" name="auto-mode" :checked="state.mode === 'claude'" @change="save({ mode: 'claude' })">
        <span><strong>Claude</strong> — {{ t("une phrase et des mots-clés pour toutes les photos ; les photos sont envoyées à Anthropic (environ 0,7 centime par photo).") }}</span></label>
    </div>
    <div v-if="state.mode === 'claude'" class="row">
      <input v-model="apiKey" type="password" autocomplete="off" :placeholder="state.has_key ? t('Clé enregistrée (la remplacer…)') : t('Clé d’API Anthropic (sk-ant-…)')">
      <button class="btn small" type="button" :disabled="!apiKey" @click="save({ api_key: apiKey })">{{ t("Enregistrer") }}</button>
    </div>
    <div class="row">
      <button class="btn small" type="button" :disabled="state.running" @click="runNow">
        <i class="fas" :class="state.running ? 'fa-spinner fa-spin' : 'fa-play'"></i> {{ t("Essayer maintenant") }}</button>
      <span class="small muted">{{ t("{done} photo(s) avec des propositions, dont {described} décrite(s)", { done: state.done, described: state.described }) }}</span>
    </div>
  </section>
</template>

<style scoped>
.auto { margin-top: 1rem; display: grid; gap: .5rem; }
.check { display: flex; gap: .4rem; align-items: flex-start; }
.modes { display: grid; gap: .3rem; }
.row { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
.row input { flex: 1; min-width: 200px; }
.warn { color: var(--warn); }
</style>
