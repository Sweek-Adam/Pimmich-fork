<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { currentLang, t } from "../i18n";
import { notify, run } from "../toast";

interface Countdown { title: string; date: string; yearly: boolean }
const url = ref("");
const countdowns = ref<Countdown[]>([]);
const preview = ref<{ title: string; when: string; all_day: boolean }[] | null>(null);
const add = reactive({ title: "", date: "", yearly: false });

async function load(withPreview = false) {
  const d = await get<{ url: string; countdowns: Countdown[]; preview: { title: string; when: string; all_day: boolean }[] }>(
    `/api/calendar${withPreview ? "?preview=1" : ""}`);
  url.value = d.url;
  countdowns.value = d.countdowns;
  if (withPreview) preview.value = d.preview;
}

async function saveUrl() {
  const done = await run(() => post("/api/calendar", { url: url.value }));
  if (done) load(true);
}

async function saveCountdowns(list: Countdown[]) {
  const done = await run(() => post("/api/calendar", { countdowns: list }));
  if (done) countdowns.value = list;
}

function addCountdown() {
  if (!add.title.trim() || !add.date) return notify(t("Indiquez un nom et une date."), true);
  saveCountdowns([...countdowns.value, { title: add.title.trim(), date: add.date, yearly: add.yearly }]);
  Object.assign(add, { title: "", date: "", yearly: false });
}

const when = (iso: string, allDay: boolean) => new Date(iso).toLocaleString(currentLang(), allDay
  ? { weekday: "long", day: "numeric", month: "long" } : { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

onMounted(() => load(false));
</script>

<template>
  <section class="card agenda">
    <div class="card-head"><h2><i class="fas fa-calendar-alt"></i>{{ t("Agenda et comptes à rebours") }}</h2></div>
    <label class="field">{{ t("Agenda (adresse iCal secrète)") }}
      <div class="row"><input v-model="url" type="url" class="spacer" placeholder="https://calendar.google.com/…/basic.ics">
        <button class="btn" type="button" @click="saveUrl">{{ t("Enregistrer et vérifier") }}</button></div></label>
    <p class="small muted">{{ t("Google Agenda : Paramètres > votre agenda > « Adresse secrète au format iCal ». Lecture seule, sans connexion de compte.") }}</p>
    <ul v-if="preview" class="list">
      <li v-for="e in preview" :key="e.when + e.title"><strong>{{ e.title }}</strong> <span class="muted small">· {{ when(e.when, e.all_day) }}</span></li>
      <li v-if="!preview.length" class="muted">{{ t("Aucun événement dans les 7 prochains jours.") }}</li>
    </ul>
    <h3>{{ t("Comptes à rebours") }}</h3>
    <ul class="list">
      <li v-for="(c, i) in countdowns" :key="c.title + c.date">
        <span class="spacer">{{ c.title }} <span class="muted small">· {{ c.date }}<template v-if="c.yearly"> · {{ t("chaque année") }}</template></span></span>
        <button class="btn small danger" type="button" @click="saveCountdowns(countdowns.filter((_, j) => j !== i))">{{ t("Retirer") }}</button>
      </li>
    </ul>
    <form class="row add" @submit.prevent="addCountdown">
      <input v-model="add.title" type="text" maxlength="80" class="spacer" :placeholder="t('Ex : Vacances, Mariage de Julie, Noël')">
      <input v-model="add.date" type="date">
      <label class="check"><input v-model="add.yearly" type="checkbox">{{ t("chaque année") }}</label>
      <button class="btn primary" type="submit"><i class="fas fa-plus"></i>{{ t("Ajouter") }}</button>
    </form>
  </section>
</template>

<style scoped>
.agenda { margin-top: 1rem; }
.field { display: grid; gap: .3rem; font-weight: 600; font-size: .9rem; }
input[type="url"], input[type="text"], input[type="date"] { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; min-width: 0; }
h3 { font-size: 1rem; margin: 1rem 0 .4rem; }
.list { list-style: none; padding: 0; margin: .5rem 0; }
.list li { display: flex; align-items: center; gap: .5rem; padding: .4rem 0; border-bottom: 1px solid var(--border); }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.check { display: flex; align-items: center; gap: .3rem; }
.add { margin-top: .6rem; }
</style>
