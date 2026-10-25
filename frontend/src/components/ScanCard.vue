<script setup lang="ts">
import { ref } from "vue";
import { post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

// Scanner de vieilles photos papier : photo du tirage -> aperçu redressé et ravivé -> ajout au cadre
const busy = ref(false);
const scanId = ref<string | null>(null);
const rotate = ref(0);
const input = ref<HTMLInputElement | null>(null);

async function send(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  busy.value = true;
  const form = new FormData();
  form.append("photo", file);
  try {
    const r = await (await fetch("/api/scan", { method: "POST", body: form, credentials: "same-origin" })).json();
    notify(r.message, !r.success);
    if (r.success) { scanId.value = r.id; rotate.value = 0; }
  } catch (e) { notify((e as Error).message, true); } finally {
    busy.value = false;
    if (input.value) input.value.value = "";
  }
}
async function keep() {
  if (!scanId.value) return;
  const r = await run(() => post(`/api/scan/${scanId.value}`, { rotate: rotate.value }));
  if (r) scanId.value = null;
}
async function drop() {
  if (scanId.value) await post(`/api/scan/${scanId.value}`, {}, "DELETE").catch(() => undefined);
  scanId.value = null;
}
</script>

<template>
  <section class="card scan">
    <div class="card-head"><h2><i class="fas fa-camera-retro"></i>{{ t("Scanner une photo papier") }}</h2></div>
    <p class="small muted">{{ t("Posez le tirage sur une table sombre et prenez-le en photo, bien éclairé et sans reflet : le cadre trouve ses bords, le redresse et ravive ses couleurs passées.") }}</p>
    <label v-if="!scanId" class="btn primary">
      <i class="fas" :class="busy ? 'fa-spinner fa-spin' : 'fa-camera'"></i> {{ busy ? t("Traitement...") : t("Photographier un tirage") }}
      <input ref="input" type="file" accept="image/*" capture="environment" hidden :disabled="busy" @change="send"></label>
    <template v-else>
      <div class="preview"><img :src="`/api/scan/${scanId}.jpg`" :style="{ transform: `rotate(${rotate}deg)` }" alt=""></div>
      <div class="row">
        <button class="btn" type="button" :title="t('Tourner')" @click="rotate = (rotate + 90) % 360"><i class="fas fa-redo"></i> {{ t("Tourner") }}</button>
        <button class="btn primary" type="button" @click="keep"><i class="fas fa-check"></i> {{ t("Ajouter au cadre") }}</button>
        <button class="btn" type="button" @click="drop"><i class="fas fa-times"></i> {{ t("Recommencer") }}</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.scan { margin-top: 1rem; display: grid; gap: .6rem; justify-items: start; }
.preview { width: 100%; display: flex; justify-content: center; background: var(--surface-2); border-radius: 12px; padding: 1rem; overflow: hidden; }
.preview img { max-width: 100%; max-height: 360px; transition: transform .3s; }
.row { display: flex; gap: .5rem; flex-wrap: wrap; }
</style>
