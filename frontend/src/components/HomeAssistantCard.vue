<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Home Assistant par MQTT (administrateurs) : le mot de passe n'est jamais renvoyé, on sait seulement s'il existe
interface Ha { enabled: boolean; host: string; port: number; user: string; has_password: boolean; device_name: string; connected: boolean }
const ha = ref<Ha | null>(null);
const form = reactive({ enabled: false, host: "", port: 1883, user: "", password: "", device_name: "" });

async function load() {
  ha.value = await get<Ha>("/api/homeassistant");
  Object.assign(form, { enabled: ha.value.enabled, host: ha.value.host, port: ha.value.port, user: ha.value.user, password: "", device_name: ha.value.device_name });
}

async function save() {
  if (await run(() => post("/api/homeassistant", { ...form }))) window.setTimeout(() => load().catch(() => {}), 3000);
}

onMounted(() => load().catch(() => (ha.value = null)));
</script>

<template>
  <section v-if="ha" class="card ha">
    <div class="card-head">
      <h2><i class="fas fa-home"></i>{{ t("Home Assistant (MQTT)") }}</h2>
      <span v-if="ha.enabled" class="pill" :class="ha.connected ? 'ok' : 'warn'">{{ ha.connected ? t("connecté") : t("non connecté") }}</span>
    </div>
    <p class="small muted">{{ t("Le cadre apparaît tout seul dans Home Assistant : interrupteur du diaporama (pour l'endormir ou le réveiller), choix de l'ambiance, photo suivante, et un champ « Alerte » dont le texte s'affiche aussitôt sur le cadre (ex. « La porte du garage est ouverte »).") }}</p>
    <label class="check"><input v-model="form.enabled" type="checkbox" class="switch">{{ t("Activer") }}</label>
    <div class="fields">
      <label>{{ t("Serveur MQTT") }}<input v-model="form.host" type="text" placeholder="homeassistant.local" maxlength="120"></label>
      <label>{{ t("Port") }}<input v-model.number="form.port" type="number" min="1" max="65535"></label>
      <label>{{ t("Utilisateur") }}<input v-model="form.user" type="text" autocomplete="off" maxlength="120"></label>
      <label>{{ t("Mot de passe") }}<input v-model="form.password" type="password" autocomplete="new-password"
        :placeholder="ha.has_password ? t('Mot de passe enregistré (laisser vide pour le garder)') : ''"></label>
      <label>{{ t("Nom du cadre") }}<input v-model="form.device_name" type="text" placeholder="Pimmich" maxlength="120"></label>
    </div>
    <p class="small muted">{{ t("Dans Home Assistant : ajoutez l'intégration MQTT (avec le module Mosquitto), puis utilisez ici le même utilisateur.") }}</p>
    <button class="btn primary" type="button" @click="save"><i class="fas fa-check"></i>{{ t("Enregistrer") }}</button>
  </section>
</template>

<style scoped>
.ha { margin-top: 1rem; }
.pill { font-size: .8rem; font-weight: 700; padding: .15rem .6rem; border-radius: 999px; background: var(--surface-2); }
.pill.ok { color: var(--ok); } .pill.warn { color: var(--warn); }
.check { display: flex; align-items: center; gap: .5rem; margin: .6rem 0; font-weight: 600; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .6rem; margin: .4rem 0 .6rem; }
.fields label { display: grid; gap: .25rem; font-size: .9rem; font-weight: 600; }
input[type="text"], input[type="number"], input[type="password"] { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .6rem; min-width: 0; }
</style>
