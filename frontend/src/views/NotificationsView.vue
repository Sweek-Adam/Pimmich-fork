<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface Notify { enabled: boolean; url: string | null; app_url: string | null; server: string; events: { key: string; label: string; on: boolean }[] }

const data = ref<Notify | null>(null);
const qr = ref("");

async function load() {
  data.value = await get<Notify>("/api/notify");
  if (data.value.url) qr.value = `/api/notify/qr.png?t=${Date.now()}`;
}

async function save(extra: Record<string, unknown> = {}) {
  if (!data.value) return;
  await run(() => post("/api/notify", { enabled: data.value!.enabled, server: data.value!.server, ...extra }));
  load();
}

async function copy() {
  try {
    await navigator.clipboard.writeText(data.value?.url || "");
    notify(t("Copié."));
  } catch {
    // copie manuelle
  }
}

async function newTopic() {
  if (!window.confirm(t("Changer de canal (les téléphones abonnés devront s'abonner de nouveau)"))) return;
  await run(() => post("/api/notify/new_topic"));
  load();
}

onMounted(load);
</script>

<template>
  <div v-if="!data" class="card"><div class="skeleton" style="height: 220px"></div></div>
  <section v-else class="card">
    <div class="card-head"><h2><i class="fas fa-bell"></i>{{ t("Notifications sur votre téléphone") }}</h2></div>
    <p class="small muted">{{ t("Le cadre vous prévient sur votre téléphone (photo d'invité à valider, problème...). Gratuit et sans compte, avec l'application ntfy.") }}</p>
    <label class="toggle"><input v-model="data.enabled" type="checkbox" class="switch" @change="save()"><strong>{{ t("Activer les notifications") }}</strong></label>
    <div v-if="data.enabled && data.url" class="setup">
      <img :src="qr" :alt="t('QR code du canal de notifications')" class="qr">
      <ol>
        <li>{{ t("Installez l'application « ntfy » (App Store ou Google Play).") }}</li>
        <li>{{ t("Dans ntfy, touchez « + » puis collez l'adresse ci-dessous (ou ouvrez le lien sur le téléphone) :") }}
          <div class="row url"><code>{{ data.url }}</code>
            <button class="btn small" type="button" @click="copy">{{ t("Copier") }}</button>
            <a v-if="data.app_url" class="btn small" :href="data.app_url">{{ t("Ouvrir dans ntfy") }}</a></div></li>
        <li>{{ t("Envoyez une notification de test pour vérifier.") }}
          <button class="btn small" type="button" @click="run(() => post('/api/notify/test'))"><i class="fas fa-paper-plane"></i>{{ t("Tester") }}</button></li>
      </ol>
    </div>
    <div v-if="data.enabled" class="events">
      <h3>{{ t("Me prévenir pour") }}</h3>
      <label v-for="e in data.events" :key="e.key" class="check">
        <input v-model="e.on" type="checkbox" @change="save({ events: { [e.key]: e.on } })">{{ e.label }}</label>
    </div>
    <details class="advanced">
      <summary>{{ t("Options avancées") }}</summary>
      <label class="field">{{ t("Serveur ntfy (si vous hébergez le vôtre)") }}
        <input v-model="data.server" type="url" placeholder="https://ntfy.sh" @change="save()"></label>
      <button class="btn small" type="button" @click="newTopic">{{ t("Changer de canal (les téléphones abonnés devront s'abonner de nouveau)") }}</button>
    </details>
  </section>
</template>

<style scoped>
.toggle { display: flex; align-items: center; gap: .8rem; margin: 1rem 0; cursor: pointer; }
.setup { display: flex; gap: 1.2rem; align-items: flex-start; flex-wrap: wrap; margin-top: .5rem; }
.qr { width: 160px; height: 160px; background: #fff; border-radius: 12px; padding: .4rem; border: 1px solid var(--border); }
.setup ol { flex: 1; min-width: 240px; display: grid; gap: .7rem; padding-left: 1.2rem; margin: 0; }
.url { margin-top: .4rem; }
.url code { background: var(--surface-2); padding: .25rem .5rem; border-radius: 8px; word-break: break-all; font-size: .85rem; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.events { margin-top: 1.2rem; display: grid; gap: .45rem; }
.events h3 { font-size: 1rem; margin-bottom: .2rem; }
.check { display: flex; align-items: center; gap: .5rem; }
.advanced { margin-top: 1.2rem; }
.advanced summary { cursor: pointer; color: var(--accent); font-weight: 600; }
.field { display: grid; gap: .3rem; margin: .7rem 0; font-size: .9rem; font-weight: 600; }
.field input { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; max-width: 420px; }
</style>
