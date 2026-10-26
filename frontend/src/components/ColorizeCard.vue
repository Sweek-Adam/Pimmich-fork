<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";
import { loadSettings, setValue, values } from "../settings";

// Colorisation des photos noir et blanc : installation du modèle, colorisation automatique des tirages scannés
interface State { installed: boolean; install: { running: boolean; done: number; total: number; error: string | null } }
const state = ref<State | null>(null);
let timer: number | undefined;

async function load() {
  try { state.value = await get<State>("/api/colorize"); } catch { state.value = null; }
  window.clearTimeout(timer);
  if (state.value?.install.running) timer = window.setTimeout(load, 3000);
}
async function install() { await run(() => post("/api/colorize/install")); load(); }
onMounted(() => { load(); loadSettings(); });
onUnmounted(() => window.clearTimeout(timer));
</script>

<template>
  <section v-if="state" class="card colorize">
    <div class="card-head"><h2><i class="fas fa-palette"></i>{{ t("Colorisation des photos noir et blanc") }}</h2></div>
    <p class="small muted">{{ t("Les vieilles photos noir et blanc retrouvent des couleurs douces et plausibles, calculées sur le Raspberry Pi (aucun service en ligne). La version colorisée est toujours une copie : l'original reste tel quel.") }}</p>
    <template v-if="state.installed">
      <p class="small ok"><i class="fas fa-check-circle"></i> {{ t("Colorisation installée. Dans la bibliothèque, ouvrez une photo noir et blanc et touchez « Coloriser ».") }}</p>
      <label class="check"><input type="checkbox" :checked="values.scan_colorize !== false" @change="setValue('scan_colorize', ($event.target as HTMLInputElement).checked)">
        {{ t("Coloriser aussi les tirages noir et blanc scannés (l'original noir et blanc est gardé à part)") }}</label>
    </template>
    <template v-else>
      <button class="btn primary" type="button" :disabled="state.install.running" @click="install">
        <i class="fas" :class="state.install.running ? 'fa-spinner fa-spin' : 'fa-download'"></i>
        {{ state.install.running ? t("Installation ({done}/{total})…", { done: state.install.done, total: state.install.total }) : t("Installer la colorisation (129 Mo)") }}</button>
      <p v-if="state.install.error" class="small warn">{{ state.install.error }}</p>
    </template>
  </section>
</template>

<style scoped>
.colorize { margin-top: 1rem; display: grid; gap: .5rem; justify-items: start; }
.check { display: flex; gap: .4rem; align-items: center; }
.ok { color: var(--ok); } .warn { color: var(--warn); }
</style>
