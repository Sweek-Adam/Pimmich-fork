<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Livre photo de l'année : PDF prêt à imprimer, créé en arrière-plan sur le cadre
interface Job { running: boolean; year: number | null; done: number; total: number; error: string | null; pages: number }
interface Book { year: number; size: number; created: number }
const years = ref<Record<string, number>>({});
const job = ref<Job | null>(null);
const books = ref<Book[]>([]);
const year = ref<number | null>(null);
let timer: number | undefined;

const choices = computed(() => Object.entries(years.value).map(([y, n]) => ({ year: Number(y), count: n })).sort((a, b) => b.year - a.year));
const percent = computed(() => job.value && job.value.total ? Math.round(100 * job.value.done / job.value.total) : 0);
const mb = (bytes: number) => `${(bytes / 1048576).toFixed(bytes >= 104857600 ? 0 : 1)} Mo`;

async function load() {
  try {
    const data = await get<{ years: Record<string, number>; job: Job; books: Book[] }>("/api/photobook");
    years.value = data.years; job.value = data.job; books.value = data.books;
    if (year.value === null && choices.value.length) year.value = choices.value[0].year;
    if (!data.job.running) stopPolling();
  } catch { /* hors ligne : on réessaie */ }
}
function stopPolling() { window.clearInterval(timer); timer = undefined; }
async function create() {
  if (year.value === null) return;
  const r = await run(() => post("/api/photobook", { year: year.value }));
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
      <button class="btn primary" type="button" :disabled="job?.running || year === null" @click="create">
        <i class="fas" :class="job?.running ? 'fa-spinner fa-spin' : 'fa-magic'"></i>
        {{ job?.running ? t("Création en cours...") : t("Créer le livre") }}</button>
    </div>
    <div v-if="job?.running" class="bar"><span :style="{ width: percent + '%' }"></span></div>
    <p v-if="job?.running && job.total" class="small muted">{{ t("Page {done} sur {total}", { done: job.done, total: job.total }) }}</p>
    <p v-if="!job?.running && job?.error === 'empty'" class="small warn">{{ t("Aucune photo datée de cette année-là.") }}</p>
    <p v-else-if="!job?.running && job?.error" class="small err">{{ job.error }}</p>
    <p v-for="b in books" :key="b.year" class="small">
      <a class="btn small" :href="`/api/photobook/${b.year}.pdf`"><i class="fas fa-download"></i> {{ t("Télécharger le livre {year}", { year: b.year }) }}</a>
      <span class="muted"> {{ mb(b.size) }}</span></p>
  </section>
</template>

<style scoped>
.book { margin-top: 1rem; }
.row { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; margin: .6rem 0; }
.bar { height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; margin: .4rem 0; }
.bar span { display: block; height: 100%; background: var(--accent); transition: width .4s; }
.warn { color: var(--warn); } .err { color: var(--danger); }
</style>
