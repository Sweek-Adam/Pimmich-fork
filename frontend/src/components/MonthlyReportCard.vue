<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Bilan du mois par e-mail : photos reçues, affichages, cœurs, et les photos les plus aimées
interface Report { enabled: boolean; recipients: string[]; mailbox: boolean }
const state = ref<Report | null>(null);
const recipients = ref("");
const sending = ref(false);

async function load() {
  try { state.value = await get<Report>("/api/monthly_report"); recipients.value = state.value.recipients.join(", "); } catch { state.value = null; }
}
async function save(change: Record<string, unknown>) { await run(() => post("/api/monthly_report", change, "PUT")); load(); }
async function test() {
  sending.value = true;
  try { await run(() => post("/api/monthly_report/test")); } finally { sending.value = false; }
}
onMounted(load);
</script>

<template>
  <section v-if="state" class="card monthly">
    <div class="card-head"><h2><i class="fas fa-chart-pie"></i>{{ t("Bilan du mois par e-mail") }}</h2></div>
    <p class="small muted">{{ t("Le 1er de chaque mois, pour ceux qui envoient des photos : combien de photos sont arrivées et de qui, combien de fois elles ont été vues, les cœurs reçus, et les photos les plus aimées.") }}</p>
    <p v-if="!state.mailbox" class="small warn">{{ t("Configurez d'abord la boîte mail du cadre (Sources › Photos reçues par e-mail) : c'est elle qui envoie la photo.") }}</p>
    <template v-else>
      <label class="check"><input type="checkbox" :checked="state.enabled" @change="save({ enabled: ($event.target as HTMLInputElement).checked })">
        {{ t("Envoyer le bilan du mois") }}</label>
      <label class="field">{{ t("Adresses (séparées par des virgules)") }}
        <textarea v-model="recipients" rows="2" placeholder="lea@exemple.fr, tonton@exemple.fr" @change="save({ recipients })"></textarea></label>
      <button class="btn small" type="button" :disabled="sending || !state.recipients.length" @click="test">
        <i class="fas" :class="sending ? 'fa-spinner fa-spin' : 'fa-paper-plane'"></i> {{ t("Envoyer le bilan du mois dernier maintenant") }}</button>
    </template>
  </section>
</template>

<style scoped>
.monthly { margin-top: 1rem; display: grid; gap: .5rem; justify-items: start; }
.check { display: flex; gap: .4rem; align-items: center; }
.field { display: grid; gap: .2rem; width: 100%; }
.field textarea { width: 100%; font: inherit; }
.warn { color: var(--warn); }
</style>
