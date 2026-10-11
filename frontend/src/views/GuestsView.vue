<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import SettingsPage from "../components/SettingsPage.vue";
import { get, post } from "../api";
import { boot } from "../boot";
import { t } from "../i18n";
import type { Section } from "../settings";
import { notify, run } from "../toast";

const guestUrl = `http://${location.hostname}/upload`;  // la page invités reste accessible en HTTP (pas d'avertissement)
const qrStamp = Date.now();

const sections: Section[] = [
  { title: () => t("QR code pour les invités"), icon: "fa-qrcode",
    intro: () => t("Affiche en permanence sur le diaporama un QR code vers la page invités, pour envoyer des photos ou écrire un message depuis un téléphone connecté au même Wi-Fi."),
    fields: [
      { key: "show_guest_qr", label: () => t("Afficher le QR code"), type: "toggle" },
      { key: "guest_qr_position", label: () => t("Position :"), type: "select", showIf: (v) => !!v.show_guest_qr,
        options: () => [{ value: "bottom_right", label: t("En bas à droite") }, { value: "bottom_left", label: t("En bas à gauche") },
          { value: "top_right", label: t("En haut à droite") }, { value: "top_left", label: t("En haut à gauche") }] },
    ] },
  { title: () => t("Messages et réactions"), icon: "fa-comments", fields: [
    { key: "guest_messages_enabled", label: () => t("Autoriser les invités à écrire des messages"), type: "toggle",
      help: () => t("Les messages des invités s'affichent directement (5 par heure et par appareil au maximum) et disparaissent au bout de 7 jours. Vous pouvez les supprimer dans Photos > Messages.") },
    { key: "voice_messages_enabled", label: () => t("Lire les messages vocaux quand leur carte s'affiche (au plus toutes les 20 minutes)"), type: "toggle" },
    { key: "voice_volume", label: () => t("Volume des messages vocaux :"), type: "range", min: 10, max: 100, step: 5, unit: " %", showIf: (v) => !!v.voice_messages_enabled },
    { key: "guest_reactions_enabled", label: () => t("Réactions : les invités voient la photo affichée et peuvent y réagir (❤️ 😂 😮 👏)"), type: "toggle",
      help: () => t("Seulement depuis le Wi-Fi de la maison. Les messages et dessins des invités restent ensuite dans le livre d'or :") },
  ] },
];

async function share(url: string, text: string) {
  try {
    if (navigator.share) await navigator.share({ title: t("Notre cadre photo"), text, url });
    else { await navigator.clipboard.writeText(url); notify(t("Lien copié : collez-le dans un message à la famille.")); }
    post("/api/setup/mark", { step: "guests" }).catch(() => {});
  } catch { /* partage annulé */ }
}

// --- Hors de la maison (Tailscale Funnel) ---
interface Remote { installed: boolean; connected: boolean; entry_ready: boolean; enabled: boolean; link: string | null }
const remote = ref<Remote | null>(null);
const activation = ref("");
const remoteProblem = () => {
  const r = remote.value;
  if (!r) return "";
  if (!r.installed) return t("Tailscale n'est pas installé sur le cadre : https://tailscale.com/download/linux");
  if (!r.connected) return t("Tailscale est installé mais pas connecté : lancez « sudo tailscale up » sur le cadre.");
  if (!r.entry_ready) return t("Une seule fois, lancez sur le Raspberry Pi : ~/pimmich/utils/enable_remote_guests.sh");
  return "";
};
async function loadRemote() {
  try { remote.value = await get<Remote>("/api/remote_guests"); } catch { remote.value = null; }
}
async function toggleRemote(enabled: boolean) {
  activation.value = "";
  try {
    const r = await post<{ message: string }>("/api/remote_guests", { enabled });
    notify(r.message);
  } catch (e) {
    const data = (e as { data?: { activation_url?: string } }).data;
    if (data?.activation_url) activation.value = data.activation_url;
    notify((e as Error).message, true);
  }
  loadRemote();
}
async function newLink() {
  await run(() => post("/api/remote_guests/new_link"));
  loadRemote();
}

// --- Cadres de la famille ---
interface Frame { id: string; name: string; url: string; online: boolean; unauthorized?: boolean; running?: boolean; photos?: number; has_photo?: boolean }
const frames = ref<Frame[]>([]);
const codes = ref<{ token: string; label: string }[]>([]);
const newFrame = reactive({ url: "", token: "", name: "" });
const stamp = ref(Date.now());

async function loadFrames() {
  try { frames.value = (await get<{ frames: Frame[] }>("/api/frames")).frames; stamp.value = Date.now(); } catch { frames.value = []; }
}
async function loadCodes() {
  try { codes.value = (await get<{ codes: { token: string; label: string }[] }>("/api/frame/pairing")).codes; } catch { codes.value = []; }
}
async function frameAction(f: Frame, action: string) {
  await run(() => post(`/api/frames/${f.id}/${action}`));
  window.setTimeout(loadFrames, 2000);
}
async function frameMessage(f: Frame) {
  const text = window.prompt(t("Votre message :"));
  if (!text) return;
  await run(() => post(`/api/frames/${f.id}/message`, { title: "", body: text, style: "pastel" }));
}
async function framePhotos(f: Frame, event: Event) {
  const files = (event.target as HTMLInputElement).files;
  if (!files?.length) return;
  const form = new FormData();
  for (const file of Array.from(files)) form.append("photos", file);
  try {
    const response = await fetch(`/api/frames/${f.id}/photos`, { method: "POST", body: form, credentials: "same-origin" });
    const r = await response.json();
    notify(r.message, !r.success);
  } catch (e) {
    notify((e as Error).message, true);
  }
}
async function removeFrame(f: Frame) {
  if (!window.confirm(t("Retirer ce cadre ?"))) return;
  await run(() => post(`/api/frames/${f.id}`, {}, "DELETE"));
  loadFrames();
}
async function addFrame() {
  const done = await run(() => post("/api/frames", newFrame));
  if (done) { Object.assign(newFrame, { url: "", token: "", name: "" }); loadFrames(); }
}
async function newCode() {
  codes.value = (await post<{ codes: { token: string; label: string }[] }>("/api/frame/pairing", {})).codes;
}
async function removeCode(token: string) {
  codes.value = (await post<{ codes: { token: string; label: string }[] }>("/api/frame/pairing", { token }, "DELETE")).codes;
}

onMounted(() => {
  if (boot.admin) { loadRemote(); loadFrames(); loadCodes(); }
});
</script>

<template>
  <section class="card invite">
    <img :src="`/api/guest_qr.png?t=${qrStamp}`" :alt="t('QR code de la page invités')" class="qr">
    <div class="text">
      <h2><i class="fas fa-user-friends"></i> {{ t("Inviter la famille et les amis") }}</h2>
      <p class="small muted">{{ t("Les personnes connectées à votre Wi-Fi scannent ce QR code (ou ouvrent l'adresse ci-dessous) pour envoyer des photos et écrire des messages sur le cadre.") }}</p>
      <code class="url">{{ guestUrl }}</code>
      <div class="row">
        <button class="btn primary" type="button" @click="share(guestUrl, t('Envoyez vos photos et vos messages sur notre cadre photo (depuis le Wi-Fi de la maison) :'))">
          <i class="fas fa-share-alt"></i>{{ t("Partager le lien") }}</button>
        <a class="btn" href="/upload" target="_blank"><i class="fas fa-external-link-alt"></i>{{ t("Ouvrir la page invités") }}</a>
        <a class="btn" href="/upload/guestbook" target="_blank"><i class="fas fa-book"></i>{{ t("ouvrir le livre d'or") }}</a>
      </div>
      <p class="small muted">{{ t("Les photos des invités passent par « À valider » avant d'être affichées.") }}</p>
    </div>
  </section>

  <section v-if="boot.admin && remote" class="card">
    <div class="card-head"><h2><i class="fas fa-globe"></i>{{ t("Hors de la maison") }}</h2></div>
    <p class="small muted">{{ t("La famille peut aussi envoyer photos et messages depuis chez elle, avec un lien secret. Seule la page d'envoi est publiée (via Tailscale) : l'administration et vos photos ne sont jamais accessibles depuis internet. Les photos passent toujours par « À valider ».") }}</p>
    <p v-if="remoteProblem()" class="alert warning small"><i class="fas fa-exclamation-triangle"></i>{{ remoteProblem() }}</p>
    <label class="toggle"><input type="checkbox" class="switch" :checked="remote.enabled" :disabled="!!remoteProblem() && !remote.enabled"
      @change="toggleRemote(($event.target as HTMLInputElement).checked)"><strong>{{ t("Autoriser les envois depuis l'extérieur") }}</strong></label>
    <a v-if="activation" class="btn primary" :href="activation" target="_blank" rel="noopener">{{ t("Autoriser Funnel sur Tailscale") }}</a>
    <div v-if="remote.link" class="invite remote">
      <img :src="`/api/guest_qr.png?remote=1&t=${qrStamp}`" :alt="t('QR code du lien secret')" class="qr">
      <div class="text">
        <code class="url">{{ remote.link }}</code>
        <div class="row">
          <button class="btn primary" type="button" @click="share(remote.link!, t('Envoyez vos photos et vos messages sur notre cadre photo, où que vous soyez :'))">
            <i class="fas fa-share-alt"></i>{{ t("Partager le lien") }}</button>
          <button class="btn" type="button" @click="newLink"><i class="fas fa-sync-alt"></i>{{ t("Changer le lien") }}</button>
        </div>
        <p class="small muted">{{ t("« Changer le lien » rend l'ancien inutilisable (par exemple s'il a circulé trop largement).") }}</p>
      </div>
    </div>
  </section>

  <SettingsPage :sections="sections" />

  <section v-if="boot.admin" class="card frames-box">
    <div class="card-head"><h2><i class="fas fa-th"></i>{{ t("Cadres de la famille") }}</h2></div>
    <p class="small muted">{{ t("Pilotez d'ici les autres cadres Pimmich de la famille (chez Mamie, au chalet…) : voir la photo affichée, les allumer, leur envoyer des photos ou un message. Ils doivent être joignables : même réseau, ou Tailscale sur les deux cadres.") }}</p>
    <p v-if="!frames.length" class="muted">{{ t("Aucun autre cadre pour l'instant.") }}</p>
    <div class="frames">
      <article v-for="f in frames" :key="f.id" class="frame">
        <img v-if="f.online && !f.unauthorized && f.has_photo" :src="`/api/frames/${f.id}/current.jpg?t=${stamp}`" alt="">
        <div v-else class="noimg"><i class="fas fa-tv"></i></div>
        <div class="body">
          <strong>{{ f.name }}</strong>
          <span class="small muted">{{ !f.online ? t("injoignable") : f.unauthorized ? t("code refusé") : (f.running ? t("diaporama en cours") : t("en veille")) + (f.photos ? ` · ${f.photos} photos` : "") }}</span>
          <div v-if="f.online && !f.unauthorized" class="row">
            <button class="btn small" type="button" @click="frameAction(f, f.running ? 'off' : 'on')">{{ f.running ? t("Endormir") : t("Allumer") }}</button>
            <button class="btn small" type="button" @click="frameAction(f, 'next')">{{ t("Photo suivante") }}</button>
            <label class="btn small">{{ t("Envoyer des photos") }}<input type="file" accept="image/*,video/*" multiple hidden @change="framePhotos(f, $event)"></label>
            <button class="btn small" type="button" @click="frameMessage(f)">{{ t("Envoyer un message") }}</button>
          </div>
          <button class="btn small danger" type="button" @click="removeFrame(f)">{{ t("Retirer") }}</button>
        </div>
      </article>
    </div>
    <details>
      <summary>{{ t("Ajouter un cadre") }}</summary>
      <ol class="small">
        <li>{{ t("Sur l'autre cadre : Partage › Invités › « Code d'association » (ci-dessous), puis « Créer un code ».") }}</li>
        <li>{{ t("Ici : son adresse (ex. https://100.101.102.103 avec Tailscale, ou https://192.168.1.30) et ce code.") }}</li>
      </ol>
      <form class="add" @submit.prevent="addFrame">
        <label>{{ t("Adresse") }}<input v-model="newFrame.url" type="url" placeholder="https://100.101.102.103" required></label>
        <label>{{ t("Code") }}<input v-model="newFrame.token" type="text" autocomplete="off" required></label>
        <label>{{ t("Nom") }}<input v-model="newFrame.name" type="text" :placeholder="t('ex : Chez Mamie')"></label>
        <div><button class="btn primary" type="submit">{{ t("Ajouter le cadre") }}</button></div>
      </form>
    </details>
    <details>
      <summary>{{ t("Code d'association de ce cadre") }}</summary>
      <p class="small muted">{{ t("À saisir sur le cadre qui pilotera celui-ci. Retirez un code pour couper l'accès.") }}</p>
      <ul class="codes">
        <li v-for="c in codes" :key="c.token"><span class="spacer">{{ c.label }} : <code>{{ c.token }}</code></span>
          <button class="btn small danger" type="button" @click="removeCode(c.token)">{{ t("Retirer") }}</button></li>
      </ul>
      <button class="btn small" type="button" @click="newCode">{{ t("Créer un code") }}</button>
    </details>
  </section>
</template>

<style scoped>
.invite { display: flex; gap: 1.2rem; align-items: flex-start; flex-wrap: wrap; margin-bottom: 1rem; }
.invite.remote { margin: 1rem 0 0; }
.qr { width: 170px; height: 170px; background: #fff; padding: .4rem; border-radius: 12px; border: 1px solid var(--border); }
.text { flex: 1; min-width: 240px; display: grid; gap: .6rem; }
.text h2 i { color: var(--accent); }
.url { background: var(--surface-2); padding: .35rem .6rem; border-radius: 8px; word-break: break-all; font-size: .9rem; width: fit-content; max-width: 100%; }
.toggle { display: flex; align-items: center; gap: .8rem; margin: .8rem 0; cursor: pointer; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.frames-box { margin-top: 1rem; }
.frames { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .8rem; margin: .8rem 0; }
.frame { border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
.frame img, .noimg { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; background: #111; }
.noimg { display: grid; place-items: center; color: #666; font-size: 2rem; }
.frame .body { padding: .6rem .7rem; display: grid; gap: .4rem; }
details { margin-top: .8rem; }
summary { cursor: pointer; color: var(--accent); font-weight: 600; }
.add { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .6rem; align-items: end; margin-top: .6rem; }
.add label { display: grid; gap: .25rem; font-size: .9rem; font-weight: 600; }
.add input { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; }
.codes { list-style: none; padding: 0; margin: .5rem 0; }
.codes li { display: flex; gap: .5rem; align-items: center; padding: .35rem 0; }
.alert { margin: .6rem 0; }
</style>
