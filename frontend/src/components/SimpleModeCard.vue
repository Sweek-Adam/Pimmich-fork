<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

// Mode grands-parents : un lien à ouvrir sur leur téléphone, vers une page à très gros boutons
const link = ref<string | null>(null);
const name = ref("");
const stamp = ref(Date.now());

async function load() {
  try { const r = await get<{ link: string | null; name: string }>("/api/simple_link"); link.value = r.link; name.value = r.name; } catch { link.value = null; }
}
async function create(renew = false) {
  if (renew && !window.confirm(t("Changer le lien ? L'ancien ne marchera plus : il faudra rouvrir le nouveau sur le téléphone."))) return;
  const r = await run(() => post<{ success: boolean; message?: string; link: string | null; name: string }>("/api/simple_link", { name: name.value, renew }));
  if (r) { link.value = r.link; stamp.value = Date.now(); }
}
async function remove() {
  if (!window.confirm(t("Supprimer le lien ? Le téléphone ne pourra plus piloter le cadre."))) return;
  await run(() => post("/api/simple_link", {}, "DELETE"));
  link.value = null;
}
async function copy() {
  if (!link.value) return;
  try { await navigator.clipboard.writeText(link.value); notify(t("Lien copié.")); } catch { window.prompt(t("Copiez ce lien :"), link.value); }
}
onMounted(load);
</script>

<template>
  <section class="card simple">
    <div class="card-head"><h2><i class="fas fa-hand-holding-heart"></i>{{ t("Mode grands-parents") }}</h2></div>
    <p class="small muted">{{ t("Une page toute simple, à très gros boutons, pour un téléphone de la maison : voir la photo affichée, passer à la suivante, envoyer un ❤️ ou un petit mot (écrit ou dit à voix haute), allumer ou éteindre le cadre. Sans mot de passe, sur le Wi-Fi de la maison seulement.") }}</p>
    <label class="field">{{ t("Prénom affiché (« Bonjour Mamie ! »)") }}<input v-model="name" type="text" maxlength="40" :placeholder="t('ex : Mamie')" @change="link && create(false)"></label>
    <template v-if="link">
      <div class="share">
        <img :src="`/api/simple_link/qr.png?t=${stamp}`" alt="" class="qr">
        <div class="steps small">
          <p>{{ t("Scannez ce QR code avec le téléphone (sur le Wi-Fi de la maison), puis ajoutez la page à l'écran d'accueil (menu Partager › « Sur l'écran d'accueil »).") }}</p>
          <div class="row">
            <button class="btn small" type="button" @click="copy"><i class="fas fa-copy"></i> {{ t("Copier le lien") }}</button>
            <button class="btn small" type="button" @click="create(true)"><i class="fas fa-sync-alt"></i> {{ t("Changer le lien") }}</button>
            <button class="btn small danger" type="button" @click="remove"><i class="fas fa-trash-alt"></i> {{ t("Supprimer") }}</button>
          </div>
        </div>
      </div>
    </template>
    <button v-else class="btn primary" type="button" @click="create(false)"><i class="fas fa-link"></i> {{ t("Créer le lien") }}</button>
  </section>
</template>

<style scoped>
.simple { margin-top: 1rem; display: grid; gap: .6rem; justify-items: start; }
.field { display: grid; gap: .2rem; }
.share { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.qr { width: 160px; height: 160px; border-radius: 10px; background: #fff; }
.steps { flex: 1; min-width: 220px; display: grid; gap: .4rem; }
.row { display: flex; gap: .4rem; flex-wrap: wrap; }
</style>
