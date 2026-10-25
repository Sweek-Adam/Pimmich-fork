<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Photo du jour par e-mail : pour les proches qui n'ont pas de cadre
interface DailyPhoto { enabled: boolean; recipients: string[]; time: string; mailbox: boolean; last_at: number | null; last_error: string | null }
const state = ref<DailyPhoto | null>(null);
const recipients = ref("");
const sending = ref(false);

async function load() {
  try {
    state.value = await get<DailyPhoto>("/api/daily_photo");
    recipients.value = state.value.recipients.join(", ");
  } catch { state.value = null; }
}
async function save(change: Record<string, unknown>) {
  await run(() => post("/api/daily_photo", change, "PUT"));
  load();
}
async function test() {
  sending.value = true;
  try { await run(() => post("/api/daily_photo/test")); } finally { sending.value = false; load(); }
}

onMounted(load);
</script>

<template>
  <section v-if="state" class="card daily">
    <div class="card-head"><h2><i class="fas fa-envelope-open-text"></i>{{ t("Photo du jour par e-mail") }}</h2></div>
    <p class="small muted">{{ t("Pour les proches qui n'ont pas de cadre : chaque jour, une photo par e-mail (un souvenir « ce jour-là » de préférence, sinon une photo arrivée récemment ou une des plus aimées). Les destinataires ne voient pas les adresses des autres.") }}</p>
    <p v-if="!state.mailbox" class="small warn">{{ t("Configurez d'abord la boîte mail du cadre (Sources › Photos reçues par e-mail) : c'est elle qui envoie la photo.") }}</p>
    <template v-else>
      <label class="check"><input type="checkbox" :checked="state.enabled" @change="save({ enabled: ($event.target as HTMLInputElement).checked })">
        {{ t("Envoyer la photo du jour") }}</label>
      <label class="field">{{ t("Adresses (séparées par des virgules)") }}
        <textarea v-model="recipients" rows="2" placeholder="mamie@exemple.fr, tonton@exemple.fr" @change="save({ recipients })"></textarea></label>
      <div class="row">
        <label class="small">{{ t("Chaque jour à") }} <input type="time" :value="state.time" @change="save({ time: ($event.target as HTMLInputElement).value })"></label>
        <button class="btn small" type="button" :disabled="sending || !state.recipients.length" @click="test">
          <i class="fas" :class="sending ? 'fa-spinner fa-spin' : 'fa-paper-plane'"></i> {{ t("Envoyer maintenant") }}</button>
      </div>
      <p v-if="state.last_error" class="small warn">{{ t("Dernier envoi impossible :") }} {{ state.last_error }}</p>
      <p v-else-if="state.last_at" class="small muted">{{ t("Dernier envoi : {date}", { date: new Date(state.last_at * 1000).toLocaleString() }) }}</p>
    </template>
  </section>
</template>

<style scoped>
.daily { margin-top: 1rem; display: grid; gap: .5rem; }
.check { display: flex; gap: .4rem; align-items: center; }
.field { display: grid; gap: .2rem; }
.field textarea { width: 100%; font: inherit; }
.row { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; }
.warn { color: var(--warn); }
</style>
