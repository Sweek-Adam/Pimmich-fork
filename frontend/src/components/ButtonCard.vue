<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { get } from "../api";
import { currentLang, t } from "../i18n";
import { values } from "../settings";

// Bouton physique : état de la bibliothèque GPIO, broche surveillée et dernier appui (pour vérifier le câblage)
interface ButtonState { available: boolean; pin: number | null; error: string | null; last_press: number | null }
const state = ref<ButtonState | null>(null);
let timer: number | undefined;

async function load() {
  try { state.value = await get<ButtonState>("/api/gpio_button"); } catch { state.value = null; }
}

const when = (at: number) => new Date(at * 1000).toLocaleTimeString(currentLang());

onMounted(() => { load(); timer = window.setInterval(load, 3000); });
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section v-if="state" class="card button">
    <div class="card-head"><h2><i class="fas fa-dot-circle"></i>{{ t("Bouton physique") }}</h2></div>
    <p v-if="!state.available" class="small warn">{{ t("Bibliothèque GPIO absente. Sur le Raspberry Pi, lancez une fois :") }}
      <code>sudo apt install -y liblgpio-dev swig &amp;&amp; ~/pimmich/venv/bin/pip install rpi-lgpio</code> {{ t("puis redémarrez l'application.") }}</p>
    <template v-else-if="values.button_enabled">
      <p v-if="state.error" class="small err">{{ t("Broche GPIO {pin} inutilisable :", { pin: String(values.button_pin) }) }} {{ state.error }}</p>
      <p v-else-if="state.pin !== null" class="small ok"><i class="fas fa-check-circle"></i> {{ t("Bouton surveillé sur la broche GPIO {pin}.", { pin: state.pin }) }}</p>
      <p v-else class="small muted">{{ t("Activation en cours…") }}</p>
      <p class="small">{{ t("Dernier appui :") }} <strong>{{ state.last_press ? when(state.last_press) : t("aucun pour l'instant") }}</strong></p>
    </template>
    <p v-else class="small muted">{{ t("Le bouton n'est pas activé.") }}</p>
    <p class="small muted">{{ t("Câblage : une patte du bouton sur la broche choisie (numérotation BCM, GPIO 23 = broche physique 16), l'autre sur une masse (GND, par exemple la broche 14). Aucune résistance n'est nécessaire.") }}</p>
  </section>
</template>

<style scoped>
.button { margin-top: 1rem; }
.ok { color: var(--ok); } .warn { color: var(--warn); } .err { color: var(--danger); }
code { background: var(--surface-2); padding: .1rem .35rem; border-radius: 6px; word-break: break-all; }
</style>
