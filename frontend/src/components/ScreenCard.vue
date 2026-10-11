<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { loadSettings, setValue, values } from "../settings";
import { notify, run } from "../toast";

// Résolution forcée (modes de l'écran) et capteur d'orientation (mode automatique)
interface Mode { width: number; height: number; refresh: number; text: string }
const modes = ref<Mode[] | null>(null);
const chosen = ref("");
const sensor = ref<{ sensor: string | null; seen: string | null } | null>(null);
let timer: number | undefined;

const names = (): Record<string, string> => ({
  landscape: t("Paysage (Horizontal)"), portrait: t("Portrait (Vertical)"),
  landscape_flipped: t("Paysage retourné"), portrait_flipped: t("Portrait retourné"),
});

async function loadModes() {
  try {
    modes.value = (await get<{ resolutions: Mode[] }>("/api/get_available_resolutions")).resolutions;
    if (modes.value.length) chosen.value = modes.value[0].text;
  } catch (e) {
    modes.value = [];
    notify((e as Error).message, true);
  }
}

async function apply() {
  const mode = modes.value?.find((m) => m.text === chosen.value);
  if (!mode) return;
  if (await run(() => post("/api/set_resolution", { width: mode.width, height: mode.height }))) loadSettings();
}

async function detect() {
  try {
    const d = await get<{ width: number; height: number }>("/get_current_resolution");
    setValue("display_width", d.width);
    setValue("display_height", d.height);
  } catch (e) {
    notify((e as Error).message, true);
  }
}

async function poll() {
  try { sensor.value = await get("/api/orientation"); } catch { sensor.value = null; }
}

async function calibrate(as: string) {
  await run(() => post("/api/orientation/calibrate", { as }));
  poll();
}

watch(() => values.screen_orientation, (mode) => {
  window.clearInterval(timer);
  if (mode === "auto") { poll(); timer = window.setInterval(poll, 3000); }
}, { immediate: true });
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section class="card screen">
    <div class="card-head"><h2><i class="fas fa-expand"></i>{{ t("Résolution de l'écran") }}</h2></div>
    <p class="small muted">{{ t("Force une résolution spécifique. Utile si l'écran n'est pas détecté correctement au démarrage.") }}</p>
    <div class="row">
      <template v-if="modes?.length">
        <select v-model="chosen" class="spacer"><option v-for="m in modes" :key="m.text" :value="m.text">{{ m.text }}</option></select>
        <button class="btn primary" type="button" @click="apply">{{ t("Appliquer") }}</button>
      </template>
      <button v-else class="btn" type="button" @click="loadModes"><i class="fas fa-list"></i>{{ t("Voir les résolutions de l'écran") }}</button>
      <button class="btn" type="button" :title="t('Détecter la résolution de l\'écran actif')" @click="detect"><i class="fas fa-search"></i>{{ t("Détecter") }}</button>
    </div>
    <p v-if="modes && !modes.length" class="small muted">{{ t("Aucune résolution trouvée.") }}</p>

    <template v-if="values.screen_orientation === 'auto'">
      <h3>{{ t("Orientation automatique") }}</h3>
      <p class="small">{{ t("Branchez un petit accéléromètre I2C (MPU-6050, ADXL345 ou LIS3DH) sur le Raspberry Pi (SDA, SCL, 3,3 V, GND) et activez l'I2C (sudo raspi-config › Interface Options › I2C). Fixez-le au dos du cadre, puis mémorisez ses positions : cadre posé en paysage d'abord, puis en portrait.") }}</p>
      <p class="small"><strong>{{ t("Capteur :") }}</strong>
        {{ sensor?.sensor ? `${sensor.sensor} — ${t("position actuelle :")} ${sensor.seen ? names()[sensor.seen] : t("cadre à plat ou position non mémorisée")}` : t("non détecté") }}</p>
      <div class="row">
        <button class="btn" type="button" @click="calibrate('landscape')">{{ t("Le cadre est en paysage") }}</button>
        <button class="btn" type="button" @click="calibrate('portrait')">{{ t("Le cadre est en portrait") }}</button>
        <button class="btn" type="button" @click="calibrate('portrait_flipped')">{{ t("Portrait, mais l'image était à l'envers") }}</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.screen { margin-top: 1rem; }
select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .6rem; min-width: 0; }
h3 { font-size: 1rem; margin: 1rem 0 .4rem; }
</style>
