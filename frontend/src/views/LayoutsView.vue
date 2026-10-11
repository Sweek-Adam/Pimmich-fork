<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import SettingField from "../components/SettingField.vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { loadSettings, loaded, values, type Field } from "../settings";
import { notify, run } from "../toast";

interface Format { key: string; label: string; theme: boolean; seasonal: boolean; messages: boolean; message_only: boolean; preview: string }
interface Choice { value: string; label: string; group: string | null }
interface Preset { id: string; name: string; active: boolean; count: number }

const formats = ref<Format[]>([]);
const enabled = ref<Set<string>>(new Set());
const layout = ref("auto");
const choices = ref<Choice[]>([]);
const presets = ref<Preset[]>([]);
const presetName = ref("");
let timer: number | undefined;

const basic = computed(() => formats.value.filter((f) => !f.theme && !f.message_only));
const withMessage = computed(() => formats.value.filter((f) => f.message_only));
const themes = computed(() => formats.value.filter((f) => f.theme));
const choiceGroups = computed(() => [
  { label: "", items: choices.value.filter((c) => !c.group) },
  { label: t("Formats"), items: choices.value.filter((c) => c.group === "format") },
  { label: t("Thèmes"), items: choices.value.filter((c) => c.group === "theme") },
  { label: t("Avec un message"), items: choices.value.filter((c) => c.group === "message") },
]);

const fields: Field[] = [
  { key: "compositions_every", label: () => t("Une composition toutes les (photos) :"), type: "number", min: 0, max: 100,
    help: () => t("0 : les compositions s'enchaînent, sans photo seule entre elles. Une composition reste affichée au moins 2,5 secondes par photo (la durée du diaporama est allongée si besoin).") },
  { key: "compositions_full_photos", label: () => t("Photos entières (sans recadrage)"), type: "toggle" },
  { key: "smart_crop", label: () => t("Recadrage intelligent : garder les visages entiers"), type: "toggle",
    help: () => t("Quand une photo doit être coupée (cases des compositions, photos très larges), le cadre garde les visages au lieu du centre de l'image.") },
  { key: "compositions_include_messages", label: () => t("Inclure les messages dans les compositions"), type: "toggle" },
  { key: "compositions_seasonal", label: () => t("Thèmes de saison seulement pendant leur période (et plus fréquents à ce moment-là)"), type: "toggle" },
];

async function load() {
  const d = await get<{ formats: Format[]; enabled: string[]; layout: string; choices: Choice[] }>("/api/compositions");
  formats.value = d.formats;
  enabled.value = new Set(d.enabled);
  layout.value = d.layout;
  choices.value = d.choices;
}

async function loadPresets() {
  presets.value = (await get<{ presets: Preset[] }>("/api/layout_presets")).presets;
}

function toggle(key: string) {
  const next = new Set(enabled.value);
  if (next.has(key)) next.delete(key); else next.add(key);
  if (!next.size) return notify(t("Gardez au moins une disposition."), true);
  enabled.value = next;
  window.clearTimeout(timer);
  timer = window.setTimeout(() => run(() => post("/api/compositions", { enabled: [...enabled.value] })).then(loadPresets), 700);
}

async function chooseLayout(value: string) {
  layout.value = value;
  await run(() => post("/api/slideshow/layout", { layout: value }));
}

const selection = () => ({
  formats: [...enabled.value].filter((k) => k !== "unique"), unique: enabled.value.has("unique"), every: Number(values.compositions_every ?? 5),
});

async function savePreset(id?: string) {
  const name = id ? undefined : presetName.value.trim();
  if (!id && !name) return notify(t("Donnez un nom à cette configuration."), true);
  const d = await run(() => post<{ presets: Preset[]; message: string }>("/api/layout_presets", { name, id, selection: selection() }));
  if (d) { presets.value = d.presets; presetName.value = ""; }
}

async function activatePreset(p: Preset) {
  const d = await run(() => post<{ presets: Preset[]; message: string }>(`/api/layout_presets/${p.id}/activate`));
  if (d) { presets.value = d.presets; await load(); await loadSettings(); }
}

async function removePreset(p: Preset) {
  if (!window.confirm(t("Supprimer cette configuration ?"))) return;
  const d = await run(() => post<{ presets: Preset[]; message: string }>(`/api/layout_presets/${p.id}`, {}, "DELETE"));
  if (d) presets.value = d.presets;
}

onMounted(() => {
  load().catch((e) => notify((e as Error).message, true));
  loadPresets().catch(() => {});
  loadSettings().catch(() => {});
});
</script>

<template>
  <div class="grid grid-2 top">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-magic"></i>{{ t("Disposition du moment") }}</h2></div>
      <p class="small muted">{{ t("Choisissez une disposition à afficher une seule fois tout de suite, ou à utiliser jusqu'à nouvel ordre. « Selon mes réglages » utilise les dispositions cochées ci-dessous.") }}</p>
      <select class="layout-select" :value="layout" @change="chooseLayout(($event.target as HTMLSelectElement).value)">
        <template v-for="group in choiceGroups" :key="group.label">
          <optgroup v-if="group.label" :label="group.label">
            <option v-for="c in group.items" :key="c.value" :value="c.value">{{ c.label }}</option>
          </optgroup>
          <template v-else><option v-for="c in group.items" :key="c.value" :value="c.value">{{ c.label }}</option></template>
        </template>
      </select>
    </section>
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-bookmark"></i>{{ t("Mes configurations") }}</h2></div>
      <p class="small muted">{{ t("Enregistrez vos choix de dispositions sous un nom, puis passez de l'une à l'autre d'un clic.") }}</p>
      <ul class="presets">
        <li v-for="p in presets" :key="p.id">
          <span class="spacer"><strong>{{ p.name }}</strong> <span class="small muted">· {{ p.count }} {{ t("disposition(s)") }}</span></span>
          <span v-if="p.active" class="pill ok">{{ t("Active") }}</span>
          <button v-else class="btn small" type="button" @click="activatePreset(p)">{{ t("Activer") }}</button>
          <button class="btn icon" type="button" :title="t('Remplacer par la sélection')" @click="savePreset(p.id)"><i class="fas fa-save"></i></button>
          <button class="btn icon danger" type="button" :title="t('Supprimer')" @click="removePreset(p)"><i class="fas fa-trash-alt"></i></button>
        </li>
      </ul>
      <p v-if="!presets.length" class="small muted">{{ t("Aucune configuration enregistrée.") }}</p>
      <form class="row" @submit.prevent="savePreset()">
        <input v-model="presetName" type="text" maxlength="60" class="spacer" :placeholder="t('Nom (ex : Soirée, Calme, Noël en famille)')">
        <button class="btn" type="submit"><i class="fas fa-save"></i>{{ t("Enregistrer la sélection ci-dessous") }}</button>
      </form>
    </section>
  </div>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-th-large"></i>{{ t("Dispositions utilisées") }}</h2></div>
    <div v-if="loaded" class="options"><SettingField v-for="field in fields" :key="field.key" :field="field" /></div>
    <template v-for="group in [{ title: t('Formats'), items: basic }, { title: t('Thèmes'), items: themes },
                               { title: t('Avec un message'), items: withMessage, hint: t('Construites autour d\'un message ou d\'un dessin d\'invité : elles n\'apparaissent que lorsqu\'un message est à afficher.') }]" :key="group.title">
      <h3 class="group-title">{{ group.title }}</h3>
      <p v-if="group.hint" class="small muted">{{ group.hint }}</p>
      <div class="formats">
        <button v-for="f in group.items" :key="f.key" type="button" class="format" :class="{ on: enabled.has(f.key) }" @click="toggle(f.key)">
          <img :src="f.preview" :alt="f.label" loading="lazy">
          <span class="name">
            <i class="far" :class="enabled.has(f.key) ? 'fa-check-square' : 'fa-square'"></i>{{ f.label }}
            <i v-if="f.seasonal" class="fas fa-leaf hint" :title="t('Thème de saison')"></i>
            <i v-if="f.messages" class="fas fa-comment-dots hint" :title="t('Affiche les messages')"></i>
          </span>
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.top { margin-bottom: 1rem; }
.top .card + .card { margin-top: 0; }
.layout-select { width: 100%; margin-top: .8rem; font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .5rem .7rem; }
.presets { list-style: none; padding: 0; margin: .6rem 0; }
.presets li { display: flex; align-items: center; gap: .5rem; padding: .4rem 0; border-bottom: 1px solid var(--border); }
.presets .btn.icon { width: 2.2rem; height: 2.2rem; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
form input { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; min-width: 0; }
.options { margin-bottom: .6rem; }
.group-title { margin: 1rem 0 .6rem; font-size: 1rem; }
.formats { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: .7rem; }
.format { border: 2px solid var(--border); border-radius: 12px; padding: 0; overflow: hidden; background: var(--surface); color: var(--text); font: inherit; text-align: left; cursor: pointer; opacity: .6; transition: opacity .15s, border-color .15s; }
.format.on { border-color: var(--accent); opacity: 1; }
.format img { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
.name { display: flex; align-items: center; gap: .4rem; padding: .45rem .55rem; font-size: .88rem; font-weight: 600; }
.name i:first-child { color: var(--accent); }
.hint { color: var(--muted); font-size: .75rem; }
</style>
