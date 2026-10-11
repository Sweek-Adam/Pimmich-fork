<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify } from "../toast";

// Album intelligent : des règles (période, années, personnes, lieu, sources, favoris) au lieu d'une liste de photos
export interface Rules { from?: string; to?: string; years?: number[]; people?: string[]; people_all?: boolean; sources?: string[]; place?: string; favorites?: boolean; media?: string }
export interface SmartMeta { events: Record<string, { label: string; from: string; to: string }>; people: string[]; sources: string[]; years: number[] }

const props = defineProps<{ album: { id?: string; name: string; smart?: Rules } }>();
const emit = defineEmits<{ close: []; saved: [] }>();

const meta = ref<SmartMeta | null>(null);
const r = props.album.smart || {};
const form = reactive({
  name: props.album.name || "", period: "", from: r.from || "", to: r.to || "", years: (r.years || []).map(String),
  people: [...(r.people || [])], all: !!r.people_all, sources: [...(r.sources || [])], place: r.place || "", fav: !!r.favorites, media: r.media || "",
});
const preview = ref<{ count: number; thumbs: string[] } | null>(null);
const busy = ref(false);
let timer: number | undefined;

const rules = computed<Rules>(() => {
  const out: Rules = {};
  if (form.period === "custom") { out.from = form.from.trim(); out.to = form.to.trim(); }
  else if (form.period && meta.value) { out.from = meta.value.events[form.period].from; out.to = meta.value.events[form.period].to; }
  if (form.years.length) out.years = form.years.map(Number);
  if (form.people.length) { out.people = form.people; if (form.all) out.people_all = true; }
  if (form.sources.length) out.sources = form.sources;
  if (form.place.trim()) out.place = form.place.trim();
  if (form.fav) out.favorites = true;
  if (form.media) out.media = form.media;
  return out;
});

watch(rules, () => {
  window.clearTimeout(timer);
  timer = window.setTimeout(async () => {
    try { preview.value = await post("/api/smart_albums/preview", { rules: rules.value }); } catch { preview.value = null; }
  }, 250);
}, { deep: true, immediate: true });

async function save() {
  busy.value = true;
  try {
    const d = await post<{ message: string }>("/api/smart_albums", { id: props.album.id || null, name: form.name, rules: rules.value });
    notify(d.message);
    emit("saved");
    emit("close");
  } catch (e) {
    notify((e as Error).message, true);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  meta.value = await get<SmartMeta>("/api/smart_albums");
  if (r.from) {
    const event = Object.entries(meta.value.events).find(([, e]) => e.from === r.from && e.to === r.to);
    form.period = event ? event[0] : "custom";
  }
});
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div class="panel" role="dialog" aria-modal="true">
      <div class="card-head">
        <h2><i class="fas fa-magic"></i>{{ t("Album intelligent") }}</h2>
        <button class="btn icon" type="button" :title="t('Fermer')" @click="emit('close')"><i class="fas fa-times"></i></button>
      </div>
      <div v-if="!meta" class="skeleton" style="height: 240px"></div>
      <div v-else class="grid-form">
        <label for="sa-name">{{ t("Nom") }}</label>
        <input id="sa-name" v-model="form.name" type="text" maxlength="80" :placeholder="t('ex : Les enfants, Été 2025, Noël en famille')">

        <label for="sa-period">{{ t("Période de l'année") }}</label>
        <div class="row">
          <select id="sa-period" v-model="form.period">
            <option value="">{{ t("Toute l'année") }}</option>
            <option v-for="(e, key) in meta.events" :key="key" :value="key">{{ e.label }}</option>
            <option value="custom">{{ t("Dates précises…") }}</option>
          </select>
          <template v-if="form.period === 'custom'">
            {{ t("du") }} <input v-model="form.from" type="text" class="day" placeholder="06-21" maxlength="5">
            {{ t("au") }} <input v-model="form.to" type="text" class="day" placeholder="09-22" maxlength="5">
            <small class="muted">{{ t("(mois-jour)") }}</small>
          </template>
        </div>

        <span>{{ t("Années") }}</span>
        <div class="checks"><label v-for="y in meta.years" :key="y"><input v-model="form.years" type="checkbox" :value="String(y)"> {{ y }}</label></div>

        <template v-if="meta.people.length">
          <span>{{ t("Personnes") }}</span>
          <div>
            <div class="checks"><label v-for="p in meta.people" :key="p"><input v-model="form.people" type="checkbox" :value="p"> {{ p }}</label></div>
            <label class="small"><input v-model="form.all" type="checkbox"> {{ t("Toutes ensemble sur la photo (sinon : au moins une)") }}</label>
          </div>
        </template>

        <label for="sa-place">{{ t("Lieu") }}</label>
        <input id="sa-place" v-model="form.place" type="text" maxlength="80" :placeholder="t('ex : Biarritz, Italie')">

        <span>{{ t("Sources") }}</span>
        <div class="checks"><label v-for="s in meta.sources" :key="s"><input v-model="form.sources" type="checkbox" :value="s"> {{ s }}</label></div>

        <span>{{ t("Autres") }}</span>
        <div class="row">
          <label><input v-model="form.fav" type="checkbox"> <i class="fas fa-star star"></i> {{ t("Favoris uniquement") }}</label>
          <select v-model="form.media">
            <option value="">{{ t("Photos et vidéos") }}</option>
            <option value="photos">{{ t("Photos seulement") }}</option>
            <option value="videos">{{ t("Vidéos seulement") }}</option>
          </select>
        </div>
      </div>
      <div class="preview">
        <strong>{{ preview?.count ? t("{n} photos", { n: preview.count }) : t("Aucune pour l'instant") }}</strong>
        <div class="thumbs"><img v-for="src in preview?.thumbs || []" :key="src" :src="src" alt="" loading="lazy"></div>
      </div>
      <div class="row footer">
        <span class="spacer"></span>
        <button class="btn" type="button" @click="emit('close')">{{ t("Annuler") }}</button>
        <button class="btn primary" type="button" :disabled="busy" @click="save"><i class="fas fa-check"></i>{{ t("Enregistrer l'album") }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.backdrop { position: fixed; inset: 0; z-index: 55; background: rgba(0, 0, 0, .45); display: grid; place-items: center; padding: 1rem; }
.panel { width: min(760px, 100%); max-height: 100%; overflow-y: auto; background: var(--surface); border-radius: 18px; padding: 1rem; box-shadow: var(--shadow); }
.grid-form { display: grid; grid-template-columns: max-content 1fr; gap: .7rem 1rem; align-items: center; }
.grid-form > label, .grid-form > span { font-size: .9rem; font-weight: 600; }
.checks { display: flex; flex-wrap: wrap; gap: .3rem .9rem; }
.day { width: 5.5rem; }
.star { color: #e0a800; }
input[type="text"], select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; min-width: 0; }
.preview { display: flex; align-items: center; gap: .8rem; margin-top: .9rem; min-height: 56px; }
.thumbs { display: flex; gap: 4px; overflow: hidden; }
.thumbs img { width: 56px; height: 56px; object-fit: cover; border-radius: 8px; }
.footer { margin-top: .8rem; }
@media (max-width: 640px) { .grid-form { grid-template-columns: 1fr; } .backdrop { padding: 0; } .panel { border-radius: 0; height: 100%; } }
</style>
