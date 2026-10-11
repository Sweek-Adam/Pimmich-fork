<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import SettingsPage from "../components/SettingsPage.vue";
import { get, post } from "../api";
import { boot } from "../boot";
import { t } from "../i18n";
import type { Section } from "../settings";
import { run } from "../toast";

const devices = ref<{ index: number; name: string; hostapi: string }[]>([]);
const status = ref<{ status: string; message: string } | null>(null);
const enabled = ref(false);
const diagnostics = ref<Record<string, string> | null>(null);
let timer: number | undefined;

const sections: Section[] = [
  { title: () => t("Contrôle Vocal"), icon: "fa-microphone-alt",
    intro: () => t('Contrôlez votre diaporama à la voix avec le mot-clé "Cadre Magique".'),
    fields: [
      { key: "voice_control_engine", label: () => t("Moteur de reconnaissance"), type: "select",
        options: () => [{ value: "porcupine", label: t("Picovoice Porcupine (Recommandé, nécessite une clé API)") },
          { value: "vosk", label: t("Vosk (Totalement local, sans clé API, plus gourmand)") }] },
      { key: "voice_control_language", label: () => t("Langue de reconnaissance"), type: "select",
        options: () => [{ value: "fr", label: t("Français") }, { value: "en", label: t("Anglais") }] },
      ...(boot.admin ? [{ key: "porcupine_access_key", label: () => t("Clé d'accès Picovoice"), type: "secret" as const,
        showIf: (v: Record<string, unknown>) => v.voice_control_engine !== "vosk" }] : []),
      { key: "voice_control_device_index", label: () => t("Périphérique d'entrée audio (Microphone)"), type: "select",
        options: () => [{ value: "", label: t("Périphérique par défaut") },
          ...devices.value.map((d) => ({ value: String(d.index), label: `${d.name} (${d.hostapi})` }))] },
    ] },
  { title: () => t("Volume des Notifications Sonores"), icon: "fa-volume-up", fields: [
    { key: "notification_sound_volume", label: () => t("Volume :"), type: "range", min: 0, max: 100, step: 5, unit: " %" },
  ] },
];

async function loadStatus() {
  try { status.value = await get("/api/voice_control/status"); } catch { status.value = null; }
}

async function toggle() {
  await run(() => post("/api/voice_control/toggle", { enabled: enabled.value }));
  window.setTimeout(loadStatus, 3000);
}

async function diagnose() {
  diagnostics.value = (await get<{ diagnostics: Record<string, string> }>("/api/audio_diagnostics")).diagnostics;
}

onMounted(async () => {
  loadStatus();
  timer = window.setInterval(loadStatus, 8000);
  get<{ devices: { index: number; name: string; hostapi: string }[] }>("/api/audio_devices").then((d) => (devices.value = d.devices)).catch(() => {});
  try { enabled.value = !!(await get<{ values: Record<string, unknown> }>("/api/settings")).values.voice_control_enabled; } catch { /* */ }
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section class="card head">
    <label class="toggle"><input v-model="enabled" type="checkbox" class="switch" @change="toggle"><strong>{{ t("Activer le contrôle vocal (action immédiate)") }}</strong></label>
    <span v-if="status" class="pill" :class="status.status === 'running' || status.status === 'listening' ? 'ok' : status.status === 'stopped' ? 'off' : 'warn'">
      <span class="dot"></span>{{ status.message }}</span>
  </section>
  <SettingsPage :sections="sections">
    <section class="card diag">
      <div class="card-head"><h2><i class="fas fa-stethoscope"></i>{{ t("Diagnostic Audio") }}</h2>
        <button class="btn" type="button" @click="diagnose"><i class="fas fa-play"></i>{{ t("Lancer le diagnostic") }}</button></div>
      <template v-if="diagnostics">
        <div v-for="(text, name) in diagnostics" :key="name"><h3>{{ name }}</h3><pre>{{ text }}</pre></div>
      </template>
      <p class="small muted">{{ t("Le mot-clé « Cadre Magique » avec Porcupine demande un modèle à placer dans voice_models (voir l'interface classique).") }}</p>
    </section>
  </SettingsPage>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.toggle { display: flex; align-items: center; gap: .8rem; cursor: pointer; }
.diag { margin-top: 1rem; }
.diag h3 { font-size: .9rem; margin: .6rem 0 .3rem; }
.diag pre { background: #0f1117; color: #d6d9e3; padding: .7rem; border-radius: 10px; overflow: auto; font-size: 12px; max-height: 240px; }
</style>
