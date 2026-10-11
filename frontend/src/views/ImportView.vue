<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { currentLang, t } from "../i18n";
import { notify, run } from "../toast";

type Source = "usb" | "immich" | "samba" | "gdrive";
interface Step { percent?: number; message?: string; type?: string; stage?: string; current_photo_url?: string }

const sources = computed(() => [
  { key: "gdrive" as Source, label: t("Importer depuis Google Drive"), icon: "fab fa-google-drive" },
  { key: "immich" as Source, label: t("Importer depuis Immich"), icon: "fas fa-images" },
  { key: "samba" as Source, label: t("Importer depuis Samba"), icon: "fas fa-network-wired" },
  { key: "usb" as Source, label: t("Importer depuis la clé USB"), icon: "fab fa-usb" },
]);
const job = reactive({ source: null as Source | null, percent: 0, message: "", type: "", preview: "" });
let stream: EventSource | null = null;

function follow(url: string, onDone: () => void, stagePrefix: string) {
  stream?.close();
  stream = new EventSource(url);
  stream.onmessage = (event) => {
    let data: Step;
    try { data = JSON.parse(event.data); } catch { return; }
    job.percent = data.percent ?? job.percent;
    job.message = `${stagePrefix} ${data.message ?? ""}`;
    job.type = data.type ?? "";
    if (data.current_photo_url) job.preview = data.current_photo_url;
    if (data.type === "done" || data.stage === "PREPARING_COMPLETE") { stream?.close(); onDone(); }
    else if (data.type === "error") { stream?.close(); job.source = null; notify(data.message || t("Erreur"), true); }
  };
  stream.onerror = () => { stream?.close(); if (job.source) { job.source = null; notify(t("Erreur de connexion au serveur."), true); } };
}

function startImport(source: Source) {
  Object.assign(job, { source, percent: 0, message: "", type: "", preview: "" });
  follow(`/import-${source}`, () => {
    follow(`/prepare-photos?source=${source}`, async () => {
      await post("/api/slideshow/restart_for_update").catch(() => null);
      notify(t("Préparation terminée ! Redémarrage du diaporama..."));
      job.source = null;
      loadUploads();
    }, t("Préparation :"));
  }, t("Importation :"));
}

// --- Envoi depuis ce téléphone / cet ordinateur ---
const upload = reactive({ busy: false, percent: 0, message: "" });
const fileInput = ref<HTMLInputElement | null>(null);

async function sendPhotos() {
  const files = fileInput.value?.files;
  if (!files?.length) return notify(t("Veuillez sélectionner au moins un fichier."), true);
  const form = new FormData();
  for (const file of Array.from(files)) form.append("photos", file);
  Object.assign(upload, { busy: true, percent: 0, message: "" });
  let failed = false;
  try {
    const response = await fetch("/import-smartphone", { method: "POST", body: form, credentials: "same-origin" });
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        try {
          const data: Step = JSON.parse(part.slice(6));
          upload.percent = data.percent ?? upload.percent;
          upload.message = data.message ?? "";
          if (data.type === "error") failed = true;
        } catch { /* ligne incomplète */ }
      }
    }
    if (!failed) { notify(t("Importation réussie !")); if (fileInput.value) fileInput.value.value = ""; }
    else notify(upload.message, true);
  } catch (e) {
    notify(`${t("Erreur de communication :")} ${(e as Error).message}`, true);
  }
  upload.busy = false;
  loadUploads();
}

// --- Mes envois ---
const uploads = ref<{ name: string; thumb: string }[]>([]);
async function loadUploads() {
  try { uploads.value = (await get<{ items: { name: string; thumb: string }[] }>("/api/my_uploads")).items.slice(0, 120); } catch { uploads.value = []; }
}
async function removeUpload(name: string) {
  if (!window.confirm(t("Retirer cette photo du cadre ?"))) return;
  const done = await run(() => post(`/api/my_uploads/${encodeURIComponent(name)}`, {}, "DELETE"));
  if (done) uploads.value = uploads.value.filter((u) => u.name !== name);
}

// --- WhatsApp ---
interface Summary { photos: number; videos: number; first: string | null; last: string | null; senders: { name: string; count: number }[] }
const wa = reactive({ percent: -1, summary: null as Summary | null, selected: [] as string[], caption: "text" });
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(currentLang()) : "?");

function sendWhatsapp(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append("export", file);
  const xhr = new XMLHttpRequest();
  Object.assign(wa, { percent: 0, summary: null });
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) wa.percent = Math.round((e.loaded / e.total) * 100); };
  xhr.onload = () => {
    wa.percent = -1;
    let r: { success: boolean; message?: string; summary?: Summary };
    try { r = JSON.parse(xhr.responseText); } catch { r = { success: false, message: t("Envoi impossible.") }; }
    if (!r.success || !r.summary) return notify(r.message || t("Envoi impossible."), true);
    wa.summary = r.summary;
    wa.selected = r.summary.senders.map((s) => s.name);
  };
  xhr.onerror = () => { wa.percent = -1; notify(t("Envoi impossible."), true); };
  xhr.open("POST", "/api/whatsapp/upload");
  xhr.send(form);
}

async function importWhatsapp() {
  if (!wa.summary) return;
  const all = wa.selected.length === wa.summary.senders.length;
  const done = await run(() => post("/api/whatsapp/import", { senders: all ? [] : wa.selected, caption: wa.caption }));
  if (done) wa.summary = null;
}

onMounted(loadUploads);
onUnmounted(() => stream?.close());
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fas fa-file-import"></i>{{ t("Importation des photos") }}</h2></div>
    <div class="sources">
      <button v-for="s in sources" :key="s.key" class="btn source" type="button" :disabled="!!job.source || upload.busy" @click="startImport(s.key)">
        <i :class="[s.icon, job.source === s.key ? 'fa-spin' : '']"></i>{{ s.label }}</button>
    </div>
    <div v-if="job.source" class="progress-box">
      <div class="bar"><span :style="{ width: job.percent + '%' }"></span></div>
      <p class="small">{{ job.percent }}% · {{ job.message }}</p>
      <img v-if="job.preview" :src="job.preview" :alt="t('Photo en cours de préparation')" class="preview">
    </div>
    <p class="small muted">{{ t("L'import depuis Telegram se fait automatiquement à la réception des photos.") }}</p>
  </section>

  <div class="grid grid-2 two">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-mobile-alt"></i>{{ t("Importer depuis un Smartphone") }}</h2></div>
      <p class="small muted">{{ t("Envoyez des photos directement depuis votre téléphone via le navigateur.") }}</p>
      <form class="send" @submit.prevent="sendPhotos">
        <input ref="fileInput" type="file" accept="image/*,video/*" multiple>
        <button class="btn primary" type="submit" :disabled="upload.busy || !!job.source"><i class="fas fa-upload"></i>{{ t("Envoyer les photos") }}</button>
      </form>
      <div v-if="upload.busy" class="progress-box">
        <div class="bar"><span :style="{ width: upload.percent + '%' }"></span></div>
        <p class="small">{{ upload.percent }}% · {{ upload.message }}</p>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><h2><i class="fab fa-whatsapp"></i>{{ t("Importer une discussion WhatsApp") }}</h2></div>
      <p class="small muted">{{ t("Dans WhatsApp : ouvrez la discussion (ou le groupe familial) › nom en haut › « Exporter la discussion » › « Joindre les médias ». Envoyez le fichier .zip obtenu ici. Sur Android, avec Pimmich installé sur l'écran d'accueil, vous pouvez aussi choisir directement « Pimmich » dans le menu de partage.") }}</p>
      <input type="file" accept=".zip,application/zip" class="wa-file" @change="sendWhatsapp">
      <div v-if="wa.percent >= 0" class="progress-box"><div class="bar"><span :style="{ width: wa.percent + '%' }"></span></div></div>
      <div v-if="wa.summary" class="wa-summary">
        <strong>{{ t("{photos} photos et {videos} vidéos, du {first} au {last}", { photos: wa.summary.photos, videos: wa.summary.videos, first: day(wa.summary.first), last: day(wa.summary.last) }) }}</strong>
        <p class="small">{{ t("Expéditeurs à importer :") }}</p>
        <div class="row"><label v-for="s in wa.summary.senders" :key="s.name" class="check">
          <input v-model="wa.selected" type="checkbox" :value="s.name">{{ s.name }} ({{ s.count }})</label></div>
        <label class="field">{{ t("Légende des photos :") }}
          <select v-model="wa.caption">
            <option value="text">{{ t("Le message qui accompagne la photo") }}</option>
            <option value="both">{{ t("Le prénom de l'expéditeur et son message") }}</option>
            <option value="sender">{{ t("Le prénom de l'expéditeur") }}</option>
            <option value="none">{{ t("Aucune") }}</option>
          </select></label>
        <button class="btn primary" type="button" :disabled="!wa.selected.length" @click="importWhatsapp"><i class="fas fa-file-import"></i>{{ t("Importer") }}</button>
      </div>
    </section>
  </div>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-user-circle"></i>{{ t("Mes envois") }}</h2></div>
    <p class="small muted">{{ t("Les photos envoyées depuis ce compte s'ajoutent à votre source personnelle. Touchez la croix pour en retirer une.") }}</p>
    <p v-if="!uploads.length" class="muted">{{ t("Aucun envoi pour l'instant.") }}</p>
    <div class="uploads">
      <figure v-for="u in uploads" :key="u.name"><img :src="u.thumb" alt="" loading="lazy">
        <button type="button" :title="t('Retirer du cadre')" @click="removeUpload(u.name)">×</button></figure>
    </div>
  </section>
</template>

<style scoped>
.sources { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: .6rem; margin-bottom: .9rem; }
.source { justify-content: flex-start; border-radius: 12px; padding: .8rem 1rem; }
.source i { color: var(--accent); font-size: 1.1rem; }
.progress-box { margin: .6rem 0 .9rem; }
.bar { height: 10px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--accent); transition: width .3s; }
.preview { max-width: 260px; max-height: 160px; border-radius: 10px; margin-top: .5rem; }
.two { margin: 1rem 0; }
.two .card + .card { margin-top: 0; }
.send { display: grid; gap: .6rem; margin-top: .7rem; }
.wa-file { margin: .7rem 0; }
.wa-summary { display: grid; gap: .5rem; padding: .8rem; border-radius: 12px; background: var(--surface-2); }
.check { display: flex; align-items: center; gap: .3rem; }
.field { display: grid; gap: .25rem; font-size: .9rem; font-weight: 600; }
.field select { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; }
.uploads { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: .4rem; }
.uploads figure { margin: 0; position: relative; }
.uploads img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 8px; }
.uploads button { position: absolute; top: 4px; right: 4px; width: 26px; height: 26px; border-radius: 50%; border: 0; background: rgba(0, 0, 0, .6); color: #fff; cursor: pointer; font-size: 1rem; line-height: 1; }
</style>
