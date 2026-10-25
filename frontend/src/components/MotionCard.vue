<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { get } from "../api";
import { currentLang, t } from "../i18n";
import { values } from "../settings";

// Détecteur de mouvement : broche surveillée, dernier mouvement vu (pour vérifier le câblage), écran éteint ou non
interface MotionState { available: boolean; pin: number | null; error: string | null; last_motion: number | null; screen_off: boolean }
const state = ref<MotionState | null>(null);
let timer: number | undefined;

async function load() {
  try { state.value = await get<MotionState>("/api/motion_sensor"); } catch { state.value = null; }
}

const when = (at: number) => new Date(at * 1000).toLocaleTimeString(currentLang());

onMounted(() => { load(); timer = window.setInterval(load, 3000); });
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section v-if="state" class="card motion">
    <div class="card-head"><h2><i class="fas fa-walking"></i>{{ t("Détecteur de mouvement") }}</h2></div>
    <p v-if="!state.available" class="small warn">{{ t("Bibliothèque GPIO absente. Sur le Raspberry Pi, lancez une fois :") }}
      <code>sudo apt install -y liblgpio-dev swig &amp;&amp; ~/pimmich/venv/bin/pip install rpi-lgpio</code> {{ t("puis redémarrez l'application.") }}</p>
    <template v-else-if="values.motion_sensor_enabled">
      <p v-if="state.error" class="small err">{{ t("Broche GPIO {pin} inutilisable :", { pin: String(values.motion_sensor_pin) }) }} {{ state.error }}</p>
      <p v-else-if="state.pin !== null" class="small ok"><i class="fas fa-check-circle"></i> {{ t("Capteur surveillé sur la broche GPIO {pin}.", { pin: state.pin }) }}</p>
      <p v-else class="small muted">{{ t("Activation en cours…") }}</p>
      <p class="small">{{ t("Dernier mouvement :") }} <strong>{{ state.last_motion ? when(state.last_motion) : t("aucun pour l'instant") }}</strong>
        <span v-if="state.screen_off"> · {{ t("écran éteint (personne n'est là)") }}</span></p>
    </template>
    <p v-else class="small muted">{{ t("Le détecteur n'est pas activé.") }}</p>
    <p class="small muted">{{ t("Câblage d'un capteur PIR (HC-SR501) : VCC sur 5 V (broche 2), GND sur une masse (broche 6), OUT sur la broche choisie (GPIO 24 = broche physique 18).") }}</p>
  </section>
</template>

<style scoped>
.motion { margin-top: 1rem; }
.ok { color: var(--ok); } .warn { color: var(--warn); } .err { color: var(--danger); }
code { background: var(--surface-2); padding: .1rem .35rem; border-radius: 6px; word-break: break-all; }
</style>
