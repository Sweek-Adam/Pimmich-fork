<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { ApiError, get, post } from "../api";
import { currentLang, t } from "../i18n";
import { notify, run } from "../toast";
import { boot } from "../boot";

// --- Matériel ---
interface Hardware { model: string | null; temperature: number | null; undervoltage_now: boolean | null; undervoltage_since_boot: boolean | null; sd_errors: number | null; supply?: string }
const hw = ref<Hardware | null>(null);
const level = (ok: boolean, warn: boolean) => (ok ? "ok" : warn ? "warn" : "err");

const onPi = boot.edition !== "event";  // édition ordinateur : pas de cartes propres au Raspberry Pi

// --- Profil matériel ---
interface Profile {
  model: string; ram_mb: number | null; detected: string; selected: string; current: string; profiles: { key: string; label: string }[];
  limits: { gif_budget_mb: number; gif_items: number; compositions_ahead: number; videos_always_light: boolean; video_light_above_mb: number; video_night_above_mb: number };
  recommended: { key: string; label: string; current: unknown; recommended: unknown }[];
}
const profile = ref<Profile | null>(null);
async function loadProfile() { profile.value = await get<Profile>("/api/hardware_profile"); }
async function chooseProfile(value: string) {
  await run(() => post("/api/settings", { hardware_profile: value }));
  await loadProfile();
}
async function applyRecommended() {
  await run(() => post("/api/hardware_profile/apply"));
  await loadProfile();
}
const show = (v: unknown) => (v === true ? t("Oui") : v === false ? t("Non") : String(v));
const profileLabel = (key: string) => profile.value?.profiles.find((p) => p.key === key)?.label ?? key;

// --- Mise à jour ---
interface Update { success: boolean; current?: { sha: string; date: string }; behind?: number; changes: { title: string }[]; state?: { status?: string; previous?: string } }
const update = ref<Update | null>(null);
async function rollback() {
  if (!window.confirm(t("Revenir à la version précédente ? Pimmich va redémarrer."))) return;
  await run(() => post("/api/update/rollback"));
}

// --- Espace disque et sauvegarde Drive ---
interface Maintenance {
  disk: { free_gb: number; total_gb: number; used_percent: number; low: boolean; cleanable_count: number };
  settings: { disk_alert_free_gb: number; disk_auto_cleanup: boolean; backup_drive_enabled: boolean; backup_drive_folder: string; backup_drive_interval_hours: number; backup_drive_keep: number };
  backup: { last_success: string | null; last_attempt: string | null; last_error: string | null };
}
const maint = ref<Maintenance | null>(null);
const settings = reactive({ disk_alert_free_gb: 2, disk_auto_cleanup: false, backup_drive_enabled: false, backup_drive_folder: "", backup_drive_interval_hours: 24, backup_drive_keep: 7 });
const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString(currentLang()) : "—");
async function loadMaintenance() {
  maint.value = await get<Maintenance>("/api/maintenance/status");
  Object.assign(settings, maint.value.settings);
}
async function saveMaintenance() { await run(() => post("/api/maintenance/settings", settings)); loadMaintenance(); }
async function driveBackup() { notify(t("Sauvegarde en cours...")); await run(() => post("/api/backup/drive")); loadMaintenance(); }
async function driveRestore() {
  if (!window.confirm(t("Remplacer les réglages actuels par la dernière sauvegarde du Drive ?"))) return;
  await run(() => post("/api/backup/drive/restore"));
}

// --- Stockage des photos ---
interface Usage { percent: number; free: number; total: number }
interface Storage {
  sd: Usage; storages: { id: string; label: string; usage: Usage | null; mounted: boolean }[]; disks: { uuid: string; label: string; size: number; fstype: string }[];
  sources: Record<string, { location: string; online: boolean; bytes: number; files: number }>;
  move: { running: boolean; done: number; total: number; source: string; message?: string; ok?: boolean };
}
const storage = ref<Storage | null>(null);
const smb = reactive({ share: "", username: "", password: "" });
let storageTimer: number | undefined;
const gb = (b: number) => `${(b / 1e9).toLocaleString(currentLang(), { maximumFractionDigits: b < 1e10 ? 1 : 0 })} Go`;
const targets = computed(() => [{ value: "sd", label: t("Carte SD") }, ...(storage.value?.storages ?? []).map((s) => ({ value: s.id, label: s.label }))]);
async function loadStorage() {
  storage.value = await get<Storage>("/api/storage");
  window.clearTimeout(storageTimer);
  if (storage.value.move.running) storageTimer = window.setTimeout(loadStorage, 2000);
}
async function storageAction(url: string, body: Record<string, unknown>) { await run(() => post(url, body)); loadStorage(); }
async function moveSource(source: string, to: string, event: Event) {
  const label = targets.value.find((x) => x.value === to)?.label ?? to;
  if (!window.confirm(t("Déplacer les photos de « {source} » vers « {target} » ?", { source, target: label }))) {
    (event.target as HTMLSelectElement).value = storage.value!.sources[source].location;
    return;
  }
  storageAction("/api/storage/move", { source, to });
}
async function addSmb() {
  const done = await run(() => post("/api/storage/add", { kind: "smb", ...smb }));
  if (done) { smb.password = ""; loadStorage(); }
}

// --- Sauvegarde complète ---
interface Backups { backups: { storage: string; storage_label: string; name: string; created: string | null; photos: boolean; size: number }[]; status: { running?: boolean; done?: number; total?: number; message?: string; ok?: boolean }; storages: { id: string; label: string }[] }
const full = ref<Backups | null>(null);
const fullTarget = ref("");
const restoreFile = ref<HTMLInputElement | null>(null);
let fullTimer: number | undefined;
async function loadFull() {
  full.value = await get<Backups>("/api/backup/full/storage");
  if (!fullTarget.value && full.value.storages.length) fullTarget.value = full.value.storages[0].id;
  window.clearTimeout(fullTimer);
  if (full.value.status.running) fullTimer = window.setTimeout(loadFull, 3000);
}
async function startFull() { await run(() => post("/api/backup/full/storage", { storage: fullTarget.value })); loadFull(); }
// Sauvegarde automatique de la semaine
interface AutoBackup { settings: { enabled: boolean; storage: string; weekday: number; keep: number }; state: { last_success?: number; last_try?: number; ok?: boolean; message?: string } }
const auto = ref<AutoBackup | null>(null);
const weekdays = () => [t("lundi"), t("mardi"), t("mercredi"), t("jeudi"), t("vendredi"), t("samedi"), t("dimanche")];
async function loadAuto() {
  try { auto.value = await get<AutoBackup>("/api/backup/full/auto"); } catch { auto.value = null; }
}
async function saveAuto(change: Partial<AutoBackup["settings"]>) {
  if (!auto.value) return;
  const wanted = { ...auto.value.settings, ...change };
  if (wanted.enabled && !wanted.storage) wanted.storage = fullTarget.value || full.value?.storages[0]?.id || "";
  const r = await run(() => post<{ success: boolean; message?: string; settings: AutoBackup["settings"] }>("/api/backup/full/auto", wanted, "PUT"));
  if (r?.success) auto.value.settings = r.settings; else loadAuto();
}
async function restoreFull(url: string, init: RequestInit) {
  if (!window.confirm(t("Remplacer les réglages, comptes, messages et playlists actuels par cette sauvegarde ?"))) return;
  notify(t("Restauration en cours..."));
  try {
    const response = await fetch(url, { credentials: "same-origin", ...init });
    const d = await response.json();
    notify(d.message, !d.success);
  } catch { notify(t("Erreur de communication avec le serveur."), true); }
}
function restoreUpload() {
  const file = restoreFile.value?.files?.[0];
  if (!file) return notify(t("Aucun fichier sélectionné."), true);
  const form = new FormData();
  form.append("backup", file);
  restoreFull("/api/backup/full/restore", { method: "POST", body: form });
}

// --- HTTPS par Tailscale et carte SD ---
const https = ref<{ installed: boolean; connected: boolean; enabled: boolean; link: string | null } | null>(null);
const activation = ref("");
const sd = ref<{ log2ram: boolean } | null>(null);
const fs = ref<{ known: boolean; partition?: number; disk?: number; unallocated?: number; expandable: boolean } | null>(null);
async function loadFs() { try { fs.value = await get("/api/filesystem"); } catch { fs.value = null; } }
async function expandFs() {
  if (!window.confirm(t("Cette opération va préparer le système à étendre la partition au prochain redémarrage. Voulez-vous continuer ?"))) return;
  await run(() => post("/api/filesystem/expand"));
  loadFs();
}
async function loadHttps() { try { https.value = await get("/api/admin_https"); } catch { https.value = null; } }
async function toggleHttps(enabled: boolean) {
  activation.value = "";
  try { notify((await post<{ message: string }>("/api/admin_https", { enabled })).message); }
  catch (e) {
    const url = (e as ApiError).data?.activation_url;
    if (typeof url === "string") activation.value = url;
    notify((e as Error).message, true);
  }
  loadHttps();
}

// --- À propos : licences des composants tiers (fichiers livrés avec Pimmich quand ils existent) ---
const licences = [
  { name: "Pimmich", licence: "MIT", url: "https://github.com/Sweek-Adam/Pimmich-fork/blob/main/LICENSE" },
  { name: "Vue, Vue Router", licence: "MIT", url: "https://github.com/vuejs/core/blob/main/LICENSE" },
  { name: "Font Awesome", licence: "CC BY 4.0 · SIL OFL 1.1 · MIT", url: "/static/vendor/fontawesome/LICENSE.txt" },
  { name: "Leaflet", licence: "BSD-2-Clause", url: "/static/vendor/leaflet/LICENSE" },
  { name: "Chart.js", licence: "MIT", url: "/static/vendor/chartjs/LICENSE.md" },
  { name: "GLightbox", licence: "MIT", url: "/static/vendor/glightbox/LICENSE.md" },
  { name: "SortableJS", licence: "MIT", url: "/static/vendor/sortable/LICENSE" },
  { name: "Tailwind CSS", licence: "MIT", url: "/static/vendor/tailwind/LICENSE" },
  { name: "Caveat", licence: "SIL OFL 1.1", url: "/static/fonts/LICENSE-caveat.txt" },
  { name: "Patrick Hand", licence: "SIL OFL 1.1", url: "/static/fonts/LICENSE-patrickhand.txt" },
  { name: "Permanent Marker", licence: "Apache 2.0", url: "/static/fonts/LICENSE-permanentmarker.txt" },
  { name: "Special Elite", licence: "Apache 2.0", url: "/static/fonts/LICENSE-specialelite.txt" },
  { name: "Natural Earth", licence: t("domaine public"), url: "https://www.naturalearthdata.com/about/terms-of-use/" },
  { name: "YuNet (OpenCV Zoo)", licence: "MIT", url: "https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet" },
];

// --- Système ---
async function switchDesktop() {
  if (!window.confirm(t("Le Raspberry va redémarrer sur le bureau Raspberry Pi OS et Pimmich ne se lancera plus automatiquement. Pour revenir au mode cadre photo, utilisez le raccourci « Revenir au cadre Pimmich » sur le bureau ou dans le menu. Continuer ?"))) return;
  await run(() => post("/api/switch_to_desktop"));
}
async function switchPimmich() {
  if (!window.confirm(t("Le Raspberry Pi va redémarrer en mode cadre photo Pimmich (le bureau ne s'affichera plus). Continuer ?"))) return;
  await run(() => post("/api/switch_to_pimmich"));
}
const desktop = ref<boolean | null>(null);
const confirmSubmit = (text: string) => (event: Event) => { if (!window.confirm(text)) event.preventDefault(); };

onMounted(() => {
  get<{ desktop: boolean }>("/api/display_mode").then((d) => (desktop.value = d.desktop)).catch(() => {});
  get<Hardware>("/api/hardware").then((d) => (hw.value = d)).catch(() => {});
  get<Update>("/api/update/check").then((d) => (update.value = d)).catch((e) => (update.value = { success: false, changes: [], ...(e as ApiError).data }));
  loadMaintenance().catch(() => {});
  loadProfile().catch(() => {});
  loadStorage().catch(() => {});
  loadFull().catch(() => {});
  loadAuto();
  loadHttps();
  loadFs();
  get<{ log2ram: boolean }>("/api/sd_protection").then((d) => (sd.value = d)).catch(() => {});
});
onUnmounted(() => { window.clearTimeout(storageTimer); window.clearTimeout(fullTimer); });
</script>

<template>
  <section v-if="onPi" class="card">
    <div class="card-head"><h2><i class="fas fa-microchip"></i>{{ t("Matériel") }}</h2></div>
    <div v-if="hw" class="facts">
      <div><small>{{ t("Modèle") }}</small><strong>{{ hw.model || t("Inconnu") }}</strong></div>
      <div><small>{{ t("Température") }}</small><strong :class="hw.temperature === null ? '' : level(hw.temperature < 70, hw.temperature < 80)">{{ hw.temperature === null ? t("Inconnu") : `${hw.temperature} °C` }}</strong></div>
      <div><small>{{ t("Alimentation") }}</small><strong :class="hw.undervoltage_now === null ? '' : level(!hw.undervoltage_now && !hw.undervoltage_since_boot, !hw.undervoltage_now)">
        {{ hw.undervoltage_now === null ? t("Inconnu") : hw.undervoltage_now ? t("Insuffisante en ce moment") : hw.undervoltage_since_boot ? t("A faibli depuis le démarrage") : t("Correcte") }}</strong></div>
      <div><small>{{ t("Carte SD") }}</small><strong :class="hw.sd_errors === null ? '' : level(!hw.sd_errors, true)">{{ hw.sd_errors === null ? t("Inconnu") : hw.sd_errors ? `${hw.sd_errors} ${t("erreur(s)")}` : t("Aucune erreur") }}</strong></div>
    </div>
    <p v-if="hw?.supply" class="small muted">{{ t("Alimentation conseillée pour ce modèle :") }} {{ hw.supply }}</p>
  </section>

  <section v-if="profile && onPi" class="card">
    <div class="card-head"><h2><i class="fas fa-sliders-h"></i>{{ t("Profil matériel") }}</h2></div>
    <p class="small muted">{{ t("Pimmich s'adapte à la puissance du Raspberry Pi : mémoire des animations, compositions préparées d'avance, vidéos plus légères sur les petits modèles. Vos réglages restent prioritaires.") }}</p>
    <label class="field">{{ t("Profil") }}
      <select :value="profile.selected" @change="chooseProfile(($event.target as HTMLSelectElement).value)">
        <option value="auto">{{ t("Automatique : {profile}", { profile: profileLabel(profile.detected) }) }}</option>
        <option v-for="p in profile.profiles" :key="p.key" :value="p.key">{{ p.label }}</option>
      </select>
    </label>
    <div class="facts">
      <div><small>{{ t("Modèle") }}</small><strong>{{ profile.model }}{{ profile.ram_mb ? ` · ${Math.round(profile.ram_mb / 1024 * 10) / 10} Go` : "" }}</strong></div>
      <div><small>{{ t("Mémoire des animations (GIF, photos animées)") }}</small><strong>{{ profile.limits.gif_budget_mb }} Mo · {{ t("{count} par composition", { count: profile.limits.gif_items }) }}</strong></div>
      <div><small>{{ t("Compositions préparées d'avance") }}</small><strong>{{ profile.limits.compositions_ahead }}</strong></div>
      <div><small>{{ t("Vidéos allégées (720p)") }}</small><strong>{{ profile.limits.videos_always_light ? t("Toutes") : profile.limits.video_light_above_mb ? t("À partir de {size} Mo", { size: profile.limits.video_light_above_mb }) : t("Jamais") }}</strong></div>
    </div>
    <template v-if="profile.recommended.length">
      <p class="small"><strong>{{ t("Réglages conseillés pour ce profil :") }}</strong></p>
      <ul class="small reco">
        <li v-for="r in profile.recommended" :key="r.key">{{ r.label }} : {{ show(r.current) }} → <strong>{{ show(r.recommended) }}</strong></li>
      </ul>
      <button class="btn primary" type="button" @click="applyRecommended"><i class="fas fa-magic"></i> {{ t("Appliquer les réglages conseillés") }}</button>
    </template>
    <p v-else class="small ok">{{ t("Les réglages sont déjà ceux conseillés.") }}</p>
  </section>

  <div class="grid grid-2 two">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-cloud-download-alt"></i>{{ t("Mise à jour de l'application") }}</h2></div>
      <p class="small muted">{{ t("Pimmich se met à jour depuis GitHub puis redémarre. Si la nouvelle version ne démarre pas, le cadre revient tout seul à la version précédente.") }}</p>
      <template v-if="update">
        <p class="small">{{ t("Version installée :") }} <code>{{ update.current?.sha ? `${update.current.sha} (${(update.current.date || "").slice(0, 10)})` : "?" }}</code></p>
        <p v-if="!update.success" class="small warn">{{ t("Impossible de joindre GitHub (connexion internet ?).") }}</p>
        <p v-else class="strong" :class="update.behind ? 'accent' : 'ok'">{{ update.behind ? `${t("Mise à jour disponible :")} ${update.behind} ${t("changement(s)")}` : t("Pimmich est à jour.") }}</p>
        <ul v-if="update.changes?.length" class="changes"><li v-for="c in update.changes" :key="c.title">{{ c.title }}</li></ul>
        <p v-if="update.state?.status === 'pending'" class="small">{{ t("Dernière mise à jour en cours de validation (redémarrage).") }}</p>
        <p v-if="update.state?.status === 'rolled_back'" class="small">{{ t("Le cadre est revenu à une version précédente.") }}</p>
      </template>
      <div class="row">
        <a class="btn primary" href="/update" @click="confirmSubmit(t('Lancer la mise à jour ? Vous allez être redirigé vers la page de suivi.'))($event)"><i class="fas fa-download"></i>{{ t("Lancer la mise à jour") }}</a>
        <button v-if="update?.state?.previous" class="btn" type="button" @click="rollback"><i class="fas fa-undo"></i>{{ t("Revenir à la version précédente") }}</button>
      </div>
    </section>

    <section v-if="onPi" class="card">
      <div class="card-head"><h2><i class="fas fa-power-off"></i>{{ t("Contrôle du système") }}</h2></div>
      <div class="system">
        <form method="POST" action="/restart_app" @submit="confirmSubmit(t('Êtes-vous sûr de vouloir redémarrer UNIQUEMENT l\'application web ? Le système d\'exploitation ne sera pas redémarré.'))($event)">
          <button class="btn" type="submit"><i class="fas fa-sync-alt"></i>{{ t("Redémarrer l'application web") }}</button></form>
        <form method="POST" action="/system_reboot" @submit="confirmSubmit(t('Redémarrer le système maintenant ?'))($event)">
          <button class="btn" type="submit"><i class="fas fa-redo"></i>{{ t("Redémarrer le système") }}</button>
          <label class="check small"><input type="checkbox" name="delete_logs">{{ t("Supprimer les logs") }}</label></form>
        <form method="POST" action="/shutdown" @submit="confirmSubmit(t('Êtes-vous sûr de vouloir ÉTEINDRE le système ?'))($event)">
          <button class="btn danger" type="submit"><i class="fas fa-power-off"></i>{{ t("Éteindre le système") }}</button></form>
        <p v-if="desktop !== null" class="small muted">{{ t("Mode actuel :") }} <strong>{{ desktop ? t("bureau Raspberry Pi OS (administration seule, sans diaporama)") : t("cadre photo Pimmich") }}</strong></p>
        <button class="btn" type="button" :disabled="desktop === true" @click="switchDesktop"><i class="fas fa-desktop"></i>{{ t("Repasser sur Raspberry Pi OS (bureau)") }}</button>
        <button class="btn" type="button" :disabled="desktop === false" @click="switchPimmich"><i class="fas fa-images"></i>{{ t("Repasser sur Pimmich (cadre photo)") }}</button>
      </div>
    </section>
  </div>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-hdd"></i>{{ t("Espace disque") }}</h2></div>
    <p v-if="maint"><strong>{{ maint.disk.free_gb }} {{ t("Go libres sur") }} {{ maint.disk.total_gb }} Go</strong> ({{ maint.disk.used_percent }} % {{ t("utilisés") }})
      <span v-if="maint.disk.low" class="warn"> — {{ t("espace faible") }}</span><br>
      <span class="small muted">{{ maint.disk.cleanable_count }} {{ t("média(s) Google Drive pourraient être supprimés automatiquement.") }}</span></p>
    <div class="fields">
      <label>{{ t("Alerter sous (Go libres) :") }}<input v-model.number="settings.disk_alert_free_gb" type="number" min="0" step="0.5"></label>
      <label class="check"><input v-model="settings.disk_auto_cleanup" type="checkbox">{{ t("Libérer de la place automatiquement") }}</label>
    </div>
    <p class="small muted">{{ t("Sous le seuil, les photos et vidéos Google Drive déjà retirées du Drive sont supprimées du cadre, les plus anciennes d'abord. Les favoris ne sont jamais supprimés.") }}</p>
    <h3>{{ t("Sauvegarde automatique sur Google Drive") }}</h3>
    <p class="small muted">{{ t("Sauvegarde les réglages, comptes, playlists, favoris, invitations et messages dans un dossier de votre Google Drive (connexion rclone). Les photos ne sont pas incluses.") }}</p>
    <div class="fields">
      <label class="check"><input v-model="settings.backup_drive_enabled" type="checkbox">{{ t("Activer la sauvegarde automatique") }}</label>
      <label>{{ t("Dossier Google Drive :") }}<input v-model="settings.backup_drive_folder" type="text"></label>
      <label>{{ t("Toutes les (heures) :") }}<input v-model.number="settings.backup_drive_interval_hours" type="number" min="1"></label>
      <label>{{ t("Sauvegardes conservées :") }}<input v-model.number="settings.backup_drive_keep" type="number" min="1"></label>
    </div>
    <p v-if="maint" class="small">{{ t("Dernière sauvegarde réussie :") }} <strong>{{ fmt(maint.backup.last_success) }}</strong>
      <template v-if="maint.backup.last_error"><br><span class="warn">{{ t("Dernier échec :") }} {{ fmt(maint.backup.last_attempt) }} — {{ maint.backup.last_error }}</span></template></p>
    <div class="row">
      <button class="btn primary" type="button" @click="saveMaintenance"><i class="fas fa-check"></i>{{ t("Enregistrer ces réglages") }}</button>
      <button class="btn" type="button" @click="driveBackup"><i class="fas fa-cloud-upload-alt"></i>{{ t("Sauvegarder maintenant") }}</button>
      <button class="btn" type="button" @click="driveRestore"><i class="fas fa-history"></i>{{ t("Restaurer la dernière sauvegarde") }}</button>
    </div>
  </section>

  <section v-if="storage && onPi" class="card">
    <div class="card-head"><h2><i class="fas fa-hdd"></i>{{ t("Stockage des photos") }}</h2></div>
    <div class="supports">
      <div class="support"><strong>{{ t("Carte SD") }}</strong>
        <div class="bar"><span :style="{ width: storage.sd.percent + '%' }"></span></div><small>{{ gb(storage.sd.free) }} {{ t("libres sur") }} {{ gb(storage.sd.total) }}</small></div>
      <div v-for="s in storage.storages" :key="s.id" class="support" :class="{ off: !s.mounted }"><strong>{{ s.label }}</strong>
        <template v-if="s.usage"><div class="bar"><span :style="{ width: s.usage.percent + '%' }"></span></div><small>{{ gb(s.usage.free) }} {{ t("libres sur") }} {{ gb(s.usage.total) }}</small></template>
        <p v-else class="small warn">{{ t("Débranché") }}</p>
        <button class="btn small" type="button" @click="storageAction('/api/storage/remove', { id: s.id })">{{ t("Retirer") }}</button></div>
    </div>
    <h3>{{ t("Ajouter un support") }}</h3>
    <div class="row">
      <button v-for="d in storage.disks" :key="d.uuid" class="btn" type="button" :title="t('Le contenu actuel du disque est conservé : Pimmich range ses photos dans un dossier « pimmich ».')"
              @click="storageAction('/api/storage/add', { kind: 'disk', uuid: d.uuid })">{{ t("Utiliser ce disque") }} : {{ d.label }} ({{ gb(d.size) }}, {{ d.fstype }})</button>
      <p v-if="!storage.disks.length" class="small muted">{{ t("Aucun disque USB détecté : branchez-le puis rouvrez cet onglet.") }}</p>
    </div>
    <details><summary>{{ t("Partage réseau (NAS, ordinateur)") }}</summary>
      <div class="fields">
        <label>{{ t("Adresse") }}<input v-model="smb.share" type="text" placeholder="//nas.local/photos"></label>
        <label>{{ t("Utilisateur") }}<input v-model="smb.username" type="text" autocomplete="off"></label>
        <label>{{ t("Mot de passe") }}<input v-model="smb.password" type="password" autocomplete="new-password"></label>
      </div>
      <button class="btn" type="button" @click="addSmb">{{ t("Ajouter le partage") }}</button>
    </details>
    <h3>{{ t("Emplacement de chaque source") }}</h3>
    <div class="sources">
      <template v-for="(info, name) in storage.sources" :key="name">
        <span>{{ name }}</span>
        <span class="small muted">{{ info.online ? `${gb(info.bytes)} · ${info.files} ${t("fichiers")}` : t("support débranché") }}</span>
        <select :value="info.location" :disabled="storage.move.running || !storage.storages.length" @change="moveSource(String(name), ($event.target as HTMLSelectElement).value, $event)">
          <option v-for="o in targets" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </template>
    </div>
    <div v-if="storage.move.running" class="progress"><div class="bar"><span :style="{ width: (storage.move.total ? Math.round(100 * storage.move.done / storage.move.total) : 5) + '%' }"></span></div>
      <p class="small">{{ t("Déplacement de « {source} » : {done} / {total} fichiers", { source: storage.move.source, done: storage.move.done, total: storage.move.total || "…" }) }}</p></div>
    <p v-else-if="storage.move.message" class="small" :class="storage.move.ok === false ? 'warn' : 'ok'">{{ storage.move.message }}</p>
  </section>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-archive"></i>{{ t("Sauvegarde complète") }}</h2></div>
    <p class="small muted">{{ t("Tout ce qui fait votre cadre : réglages, comptes, playlists, messages, dessins et vocaux, livre d'or, légendes, réactions, musique et historique. Restaurable en un clic, sur ce cadre ou sur une nouvelle installation.") }}</p>
    <div class="grid grid-2">
      <div class="box">
        <h3>{{ t("Sans les photos") }}</h3>
        <a class="btn primary" href="/api/backup/full"><i class="fas fa-download"></i>{{ t("Télécharger") }}</a>
        <input ref="restoreFile" type="file" accept=".zip" class="file">
        <button class="btn" type="button" @click="restoreUpload"><i class="fas fa-upload"></i>{{ t("Restaurer ce fichier") }}</button>
      </div>
      <div class="box">
        <h3>{{ t("Avec les photos, sur un disque USB ou un NAS") }}</h3>
        <p v-if="full && !full.storages.length" class="small muted">{{ t("Ajoutez d'abord un support dans « Stockage des photos » ci-dessous.") }}</p>
        <div v-else-if="full" class="row">
          <select v-model="fullTarget"><option v-for="s in full.storages" :key="s.id" :value="s.id">{{ s.label }}</option></select>
          <button class="btn primary" type="button" :disabled="full.status.running" @click="startFull"><i class="fas fa-save"></i>{{ t("Sauvegarder maintenant") }}</button>
        </div>
        <div v-if="auto && full?.storages.length" class="auto">
          <label class="check"><input type="checkbox" :checked="auto.settings.enabled" @change="saveAuto({ enabled: ($event.target as HTMLInputElement).checked })">
            {{ t("Automatiquement chaque semaine, la nuit") }}</label>
          <div v-if="auto.settings.enabled" class="row">
            <select :value="auto.settings.storage" @change="saveAuto({ storage: ($event.target as HTMLSelectElement).value })">
              <option v-for="s in full.storages" :key="s.id" :value="s.id">{{ s.label }}</option></select>
            <select :value="auto.settings.weekday" @change="saveAuto({ weekday: Number(($event.target as HTMLSelectElement).value) })">
              <option v-for="(d, i) in weekdays()" :key="i" :value="i">{{ t("le {day}", { day: d }) }}</option></select>
            <label class="small">{{ t("Garder les") }}
              <input type="number" min="1" max="20" :value="auto.settings.keep" class="keep" @change="saveAuto({ keep: Number(($event.target as HTMLInputElement).value) })">
              {{ t("dernières") }}</label>
          </div>
          <p v-if="auto.settings.enabled && auto.state.last_try" class="small" :class="auto.state.ok ? 'ok' : 'warn'">
            {{ auto.state.ok ? t("Dernière sauvegarde automatique : {date}", { date: new Date((auto.state.last_success || 0) * 1000).toLocaleString() })
               : t("Dernier essai ({date}) : {message}", { date: new Date(auto.state.last_try * 1000).toLocaleString(), message: auto.state.message || "" }) }}</p>
          <p v-else-if="auto.settings.enabled" class="small muted">{{ t("Les photos d'origine, les réglages et les messages sont copiés quand l'écran est éteint ; les plus anciennes sauvegardes automatiques sont effacées.") }}</p>
        </div>
        <p v-if="full?.status.running" class="small">{{ t("Sauvegarde en cours : {done} / {total} fichiers", { done: full.status.done || 0, total: full.status.total || "…" }) }}</p>
        <p v-else-if="full?.status.message" class="small" :class="full.status.ok === false ? 'warn' : 'ok'">{{ full.status.message }}</p>
      </div>
    </div>
    <ul v-if="full?.backups.length" class="list">
      <li v-for="b in full.backups" :key="b.storage + b.name">
        <span class="spacer">{{ b.storage_label }} · {{ (b.created || b.name).replace("T", " ") }} · {{ gb(b.size) }}<template v-if="b.photos"> · {{ t("avec photos") }}</template></span>
        <button class="btn small" type="button" @click="restoreFull('/api/backup/full/storage/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ storage: b.storage, name: b.name }) })">{{ t("Restaurer") }}</button>
      </li>
    </ul>
    <h3>{{ t("Sauvegarde et Restauration") }}</h3>
    <div class="row">
      <a class="btn" href="/api/backup_settings"><i class="fas fa-download"></i>{{ t("Télécharger la sauvegarde") }}</a>
      <form method="POST" action="/api/restore_settings" enctype="multipart/form-data" class="row" @submit="confirmSubmit(t('Êtes-vous sûr ? La configuration actuelle sera écrasée par le contenu du fichier de sauvegarde.'))($event)">
        <input type="file" name="backup_file" accept=".json" required class="file">
        <button class="btn" type="submit"><i class="fas fa-upload"></i>{{ t("Restaurer une configuration") }}</button>
      </form>
    </div>
  </section>

  <div class="grid grid-2 two">
    <section v-if="https && onPi" class="card">
      <div class="card-head"><h2><i class="fas fa-lock"></i>{{ t("HTTPS sans avertissement (Tailscale)") }}</h2></div>
      <p class="small muted">{{ t("Ouvre l'administration à une adresse sécurisée par un vrai certificat, depuis vos appareils connectés à Tailscale (à la maison comme ailleurs). Elle n'est jamais publiée sur internet.") }}</p>
      <label class="check"><input type="checkbox" class="switch" :checked="https.enabled" :disabled="!https.installed" @change="toggleHttps(($event.target as HTMLInputElement).checked)">{{ t("Activer l'accès HTTPS par Tailscale") }}</label>
      <p v-if="!https.installed" class="small warn">{{ t("Tailscale n'est pas installé sur ce cadre.") }}</p>
      <p v-else-if="!https.connected" class="small warn">{{ t("Tailscale n'est pas connecté.") }}</p>
      <a v-if="activation" class="btn primary" :href="activation" target="_blank" rel="noopener">{{ t("Autoriser sur Tailscale") }}</a>
      <a v-if="https.link" :href="https.link" target="_blank" rel="noopener" class="link">{{ https.link }}</a>
    </section>
    <section v-if="onPi" class="card">
      <div class="card-head"><h2><i class="fas fa-sd-card"></i>{{ t("Système de Fichiers de la Carte SD") }}</h2></div>
      <h3>{{ t("Protection contre l'usure") }}</h3>
      <p v-if="sd" class="small" :class="sd.log2ram ? 'ok' : ''">{{ sd.log2ram ? t("Active : les journaux sont écrits en mémoire vive et recopiés sur la carte une fois par jour.") : t("Inactive. Pour réduire les écritures sur la carte SD, lancez une fois sur le Raspberry Pi : sudo ~/pimmich/utils/enable_sd_protection.sh puis redémarrez.") }}</p>
      <h3>{{ t("Taille de la partition") }}</h3>
      <template v-if="fs?.known">
        <p class="small">{{ t("Partition système :") }} <strong>{{ gb(fs.partition || 0) }}</strong> · {{ t("carte SD :") }} {{ gb(fs.disk || 0) }}</p>
        <p v-if="!fs.expandable" class="small ok">{{ t("Toute la carte SD est déjà utilisée : rien à agrandir.") }}</p>
        <template v-else>
          <p class="small warn">{{ gb(fs.unallocated || 0) }} {{ t("ne sont pas utilisés sur la carte SD. L'opération ne supprime aucune donnée ; l'agrandissement se termine au prochain redémarrage.") }}</p>
          <button class="btn" type="button" @click="expandFs"><i class="fas fa-expand-arrows-alt"></i>{{ t("Étendre le système de fichiers") }}</button>
        </template>
      </template>
      <p v-else class="small muted">{{ t("Taille de la carte SD inconnue.") }}</p>
    </section>
  </div>

  <section class="card about">
    <div class="card-head"><h2><i class="fas fa-info-circle"></i>{{ t("À propos") }}</h2></div>
    <div class="about-grid">
      <div class="box">
        <h3>{{ t("Pimmich, le projet d'origine") }}</h3>
        <p class="small">{{ t("Créé par Gotenash et Shenron, dans le cadre du Gadgetaulab. Merci à eux !") }}</p>
        <p class="small links">
          <a href="https://github.com/gotenash/pimmich" target="_blank" rel="noopener"><i class="fab fa-github"></i> gotenash/pimmich</a>
          <a href="https://www.gadgetaulab.fr" target="_blank" rel="noopener"><i class="fas fa-flask"></i> Gadgetaulab</a>
          <a href="https://ko-fi.com/pimmich" target="_blank" rel="noopener"><i class="fas fa-mug-hot"></i> Ko-fi</a>
        </p>
      </div>
      <div class="box">
        <h3>{{ t("Ce cadre") }}</h3>
        <p class="small">{{ t("Fork personnel de Pimmich, avec de nombreuses fonctionnalités ajoutées, pour un usage purement perso.") }}</p>
        <p class="small links">
          <a href="https://github.com/Sweek-Adam/Pimmich-fork" target="_blank" rel="noopener"><i class="fab fa-github"></i> Sweek-Adam/Pimmich-fork</a>
          <span v-if="update?.current?.sha">{{ t("Version installée :") }} <code>{{ update.current.sha }}</code></span>
        </p>
      </div>
      <div class="box">
        <h3>{{ t("Licences") }}</h3>
        <p class="small">{{ t("Pimmich est distribué sous licence MIT. Les composants tiers gardent leur propre licence :") }}</p>
        <ul class="licences small">
          <li v-for="item in licences" :key="item.name"><a :href="item.url" target="_blank" rel="noopener">{{ item.name }}</a> <span class="muted">· {{ item.licence }}</span></li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .6rem; }
.facts div { background: var(--surface-2); border-radius: 12px; padding: .6rem .8rem; display: grid; }
.facts small { color: var(--muted); }
.ok { color: var(--ok); } .warn { color: var(--warn); } .err { color: var(--danger); } .accent { color: var(--accent); }
.strong { font-weight: 700; }
.two { margin: 1rem 0; }
.two .card + .card { margin-top: 0; }
.changes { margin: .4rem 0; padding-left: 1.2rem; font-size: .88rem; }
.system { display: grid; gap: .6rem; }
.system form { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.check { display: flex; align-items: center; gap: .5rem; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .6rem; margin: .6rem 0; align-items: end; }
.fields label { display: grid; gap: .25rem; font-size: .9rem; font-weight: 600; }
.fields .check { display: flex; font-weight: 500; }
input[type="text"], input[type="number"], input[type="password"], select { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; min-width: 0; }
h3 { font-size: 1rem; margin: 1rem 0 .4rem; }
.supports { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: .6rem; }
.support { border: 1px solid var(--border); border-radius: 12px; padding: .7rem; display: grid; gap: .3rem; }
.support.off { border-color: var(--danger); }
.bar { height: 8px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--accent); }
.sources { display: grid; grid-template-columns: 1fr auto auto; gap: .4rem .8rem; align-items: center; }
@media (max-width: 640px) { .sources { grid-template-columns: 1fr auto; } .sources .small { display: none; } }
.progress { margin-top: .6rem; }
details { margin: .6rem 0; }
summary { cursor: pointer; color: var(--accent); font-weight: 600; }
.box { border: 1px solid var(--border); border-radius: 12px; padding: .8rem; display: grid; gap: .5rem; align-content: start; }
.box h3 { margin: 0; }
.auto { display: grid; gap: .4rem; border-top: 1px solid var(--border); padding-top: .5rem; }
.auto .check { display: flex; gap: .4rem; align-items: center; }
.auto .keep { width: 4rem; }
.file { font-size: .85rem; }
.list { list-style: none; padding: 0; margin: .8rem 0 0; }
.list li { display: flex; gap: .5rem; align-items: center; padding: .4rem 0; border-bottom: 1px solid var(--border); }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.link { word-break: break-all; }
.about { margin-top: 1rem; }
.about-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: .8rem; }
.links { display: flex; flex-wrap: wrap; gap: .4rem 1rem; align-items: center; }
.licences { margin: 0; padding-left: 1.1rem; display: grid; gap: .2rem; }
code { background: var(--surface-2); padding: .1rem .4rem; border-radius: 6px; }
</style>
