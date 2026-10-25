<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Livre photo de l'année : PDF prêt à imprimer, créé en arrière-plan sur le cadre
interface Job { running: boolean; kind: "book" | "calendar" | null; year: number | null; done: number; total: number; error: string | null; pages: number }
interface Book { kind: "book" | "calendar"; year: number; size: number; created: number }
const years = ref<Record<string, number>>({});
const job = ref<Job | null>(null);
const books = ref<Book[]>([]);
const year = ref<number | null>(null);
const calendarYear = ref<number>(new Date().getFullYear() + 1);
let timer: number | undefined;

const choices = computed(() => Object.entries(years.value).map(([y, n]) => ({ year: Number(y), count: n })).sort((a, b) => b.year - a.year));
const percent = computed(() => job.value && job.value.total ? Math.round(100 * job.value.done / job.value.total) : 0);
const mb = (bytes: number) => `${(bytes / 1048576).toFixed(bytes >= 104857600 ? 0 : 1)} Mo`;

async function load() {
  try {
    const data = await get<{ years: Record<string, number>; job: Job; books: Book[]; calendar_year: number }>("/api/photobook");
    years.value = data.years; job.value = data.job; books.value = data.books;
    if (!calendarTouched) calendarYear.value = data.calendar_year;
    if (year.value === null && choices.value.length) year.value = choices.value[0].year;
    if (!data.job.running) stopPolling();
  } catch { /* hors ligne : on réessaie */ }
}
let calendarTouched = false;
function touchCalendar() { calendarTouched = true; }
function stopPolling() { window.clearInterval(timer); timer = undefined; }
async function create(kind: "book" | "calendar" = "book") {
  const wanted = kind === "calendar" ? calendarYear.value : year.value;
  if (wanted === null) return;
  const r = await run(() => post("/api/photobook", { year: wanted, kind }));
  if (r) { await load(); if (!timer) timer = window.setInterval(load, 2000); }
}

onMounted(load);
onUnmounted(stopPolling);
</script>

<template>
  <section v-if="choices.length" class="card book">
    <div class="card-head"><h2><i class="fas fa-book-open"></i>{{ t("Livre photo de l'année") }}</h2></div>
    <p class="small muted">{{ t("Un PDF prêt à imprimer (A4 à l'italienne) : une couverture, les plus belles photos mois par mois (les plus aimées et les favorites d'abord, sans les photos floues ou les captures d'écran), puis l'année en chiffres.") }}</p>
    <div class="row">
      <select v-model="year" :disabled="job?.running">
        <option v-for="c in choices" :key="c.year" :value="c.year">{{ c.year }} · {{ t("{count} photos", { count: c.count }) }}</option>
      </select>
      <button class="btn primary" type="button" :disabled="job?.running || year === null" @click="create('book')">
        <i class="fas" :class="job?.running ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
        {{ job?.running && job.kind === "book" ? t("Création en cours...") : t("Créer le livre") }}</button>
    </div>
    <h3 class="sub"><i class="fas fa-calendar-alt"></i> {{ t("Calendrier photo à imprimer") }}</h3>
    <p class="small muted">{{ t("Un mois par page (A4 en portrait) : une belle photo prise ce mois-là une année précédente, et la grille des jours avec les anniversaires de la famille (page Occasions), la fête des mères et des pères.") }}</p>
    <div class="row">
      <input v-model.number="calendarYear" type="number" min="2000" max="2100" class="year" :disabled="job?.running" @input="touchCalendar">
      <button class="btn primary" type="button" :disabled="job?.running" @click="create('calendar')">
        <i class="fas" :class="job?.running && job.kind === 'calendar' ? 'fa-spinner fa-spin' : 'fa-calendar-plus'"></i>
        {{ job?.running && job.kind === "calendar" ? t("Création en cours...") : t("Créer le calendrier") }}</button>
    </div>
    <div v-if="job?.running" class="bar"><span :style="{ width: percent + '%' }"></span></div>
    <p v-if="job?.running && job.total" class="small muted">{{ t("Page {done} sur {total}", { done: job.done, total: job.total }) }}</p>
    <p v-if="!job?.running && job?.error === 'empty'" class="small warn">{{ t("Aucune photo datée de cette année-là.") }}</p>
    <p v-else-if="!job?.running && job?.error" class="small err">{{ job.error }}</p>
    <p v-for="b in books" :key="b.year" class="small">
      <a class="btn small" :href="b.kind === 'calendar' ? `/api/photobook/calendar_${b.year}.pdf` : `/api/photobook/${b.year}.pdf`"><i class="fas fa-download"></i>
        {{ b.kind === "calendar" ? t("Télécharger le calendrier {year}", { year: b.year }) : t("Télécharger le livre {year}", { year: b.year }) }}</a>
      <span class="muted"> {{ mb(b.size) }}</span></p>
  </section>
</template>

<style scoped>
.book { margin-top: 1rem; }
.row { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; margin: .6rem 0; }
.bar { height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; margin: .4rem 0; }
.bar span { display: block; height: 100%; background: var(--accent); transition: width .4s; }
.sub { margin: 1rem 0 .2rem; font-size: 1rem; }
.year { width: 6rem; }
.warn { color: var(--warn); } .err { color: var(--danger); }
</style>
