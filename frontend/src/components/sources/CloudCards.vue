<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { get, post } from "../../api";
import { boot } from "../../boot";
import { t } from "../../i18n";
import { notify, run } from "../../toast";

// --- Autres clouds (rclone) ---
interface Cloud { remotes: { name: string; label: string }[]; providers: Record<string, string>; remote: string; folders: { id: string; name: string }[]; recursive: boolean; trash: boolean; auto: boolean }
const cloud = ref<Cloud | null>(null);
const cloudFolders = ref<{ id: string; name: string }[] | null>(null);
const add = reactive({ open: false, provider: "dropbox", name: "dropbox", token: "" });
async function loadCloud() {
  cloud.value = await get<Cloud>("/api/cloud");
  cloudFolders.value = null;
  if (cloud.value.remote) {
    try { cloudFolders.value = (await get<{ folders: { id: string; name: string }[] }>("/api/cloud/folders")).folders; } catch (e) { notify((e as Error).message, true); }
  }
}
async function cloudSet(change: Record<string, unknown>, reload = false) { await run(() => post("/api/cloud", change)); if (reload) loadCloud(); }
async function toggleCloudFolder(f: { id: string; name: string }) {
  if (!cloud.value) return;
  const has = cloud.value.folders.some((x) => x.id === f.id);
  cloud.value.folders = has ? cloud.value.folders.filter((x) => x.id !== f.id) : [...cloud.value.folders, f];
  cloudSet({ folders: cloud.value.folders });
}
async function addRemote() {
  const done = await run(() => post("/api/cloud/remote", { name: add.name.trim(), provider: add.provider, token: add.token.trim() }));
  if (done) { add.open = false; add.token = ""; loadCloud(); }
}

// --- iCloud ---
const icloud = ref<{ albums: { token: string; name: string; count: number }[]; auto: boolean } | null>(null);
const icloudUrl = ref("");
async function loadIcloud() { icloud.value = await get("/api/icloud"); }
async function addAlbum() { notify(t("Lecture de l'album…")); const done = await run(() => post("/api/icloud/album", { url: icloudUrl.value.trim() })); if (done) { icloudUrl.value = ""; loadIcloud(); } }
async function icloudSet(change: Record<string, unknown>) { await run(() => post("/api/icloud", change)); loadIcloud(); }

// --- E-mail ---
interface Mail { enabled: boolean; user: string; host: string; port: number; folder: string; allowed: string[]; unknown: string; has_password: boolean; providers: Record<string, string> }
const mail = reactive({ enabled: false, user: "", password: "", host: "", port: 993, folder: "INBOX", allowed: "", unknown: "pending", has_password: false });
let providers: Record<string, string> = {};
async function loadMail() {
  const d = await get<Mail>("/api/email");
  providers = d.providers;
  Object.assign(mail, { enabled: d.enabled, user: d.user, host: d.host, port: d.port, folder: d.folder, unknown: d.unknown,
    has_password: d.has_password, allowed: d.allowed.join(", "), password: "" });
}
function guessHost() {
  const domain = mail.user.split("@")[1]?.toLowerCase();
  if (domain && providers[domain] && !mail.host) mail.host = providers[domain];
}
async function saveMail() {
  const { has_password: _hp, ...body } = mail;
  const done = await run(() => post("/api/email", body));
  if (done) loadMail();
  return done;
}
async function testMail() { if (await saveMail()) { notify(t("Connexion…")); await run(() => post("/api/email/test")); } }

// --- Photos que le cadre ne peut pas retirer du Drive ---
const denied = ref<{ remote_path: string; local: boolean; drive_url?: string }[]>([]);
async function loadDenied() { denied.value = (await get<{ files: { remote_path: string; local: boolean; drive_url?: string }[] }>("/api/gdrive/denied")).files; }

onMounted(() => {
  loadCloud().catch(() => {});
  loadIcloud().catch(() => {});
  if (boot.admin) loadMail().catch(() => {});
  loadDenied().catch(() => {});
});
</script>

<template>
  <section v-if="cloud" class="card">
    <div class="card-head"><h2><i class="fas fa-cloud"></i>{{ t("Autres clouds : Dropbox, OneDrive, pCloud...") }}</h2></div>
    <div class="row">
      <label class="field">{{ t("Compte :") }}
        <select :value="cloud.remote" @change="cloudSet({ remote: ($event.target as HTMLSelectElement).value, folders: [] }, true)">
          <option value="">{{ t("Aucun compte") }}</option>
          <option v-for="r in cloud.remotes" :key="r.name" :value="r.name">{{ r.label }} ({{ r.name }})</option></select></label>
      <button v-if="boot.admin" class="btn small" type="button" @click="add.open = !add.open">{{ t("Ajouter un compte") }}</button>
    </div>
    <ol v-if="add.open" class="steps small">
      <li>{{ t("Choisissez le service :") }}
        <select v-model="add.provider"><option v-for="(label, key) in cloud.providers" :key="key" :value="key">{{ label }}</option></select>
        {{ t("et un nom court :") }} <input v-model="add.name" type="text" maxlength="32"></li>
      <li>{{ t("Sur un ordinateur (avec un navigateur), installez rclone (rclone.org/downloads) puis lancez :") }} <code>rclone authorize "{{ add.provider }}"</code>
        {{ t("Connectez-vous dans la page qui s'ouvre, puis copiez le texte affiché entre accolades { ... }.") }}</li>
      <li>{{ t("Collez-le ici :") }}<textarea v-model="add.token" rows="3" placeholder='{"access_token":"...","token_type":"bearer",...}'></textarea>
        <button class="btn small primary" type="button" @click="addRemote">{{ t("Ajouter le compte") }}</button></li>
    </ol>
    <template v-if="cloud.remote">
      <h3>{{ t("Dossiers à afficher") }}</h3>
      <p v-if="cloudFolders === null" class="small muted">{{ t("Lecture des dossiers…") }}</p>
      <div class="folders"><label v-for="f in cloudFolders || []" :key="f.id" class="check">
        <input type="checkbox" :checked="cloud.folders.some((x) => x.id === f.id)" @change="toggleCloudFolder(f)">{{ f.name }}</label></div>
      <label class="check"><input type="checkbox" :checked="cloud.recursive" @change="cloudSet({ recursive: ($event.target as HTMLInputElement).checked })">{{ t("Inclure les sous-dossiers") }}</label>
      <label class="check"><input type="checkbox" :checked="cloud.trash" @change="cloudSet({ trash: ($event.target as HTMLInputElement).checked })">{{ t("Retirer les photos du cloud une fois importées (elles restent dans sa corbeille 30 jours)") }}</label>
      <label class="check"><input type="checkbox" :checked="cloud.auto" @change="cloudSet({ auto: ($event.target as HTMLInputElement).checked })">{{ t("Synchroniser automatiquement (toutes les heures)") }}</label>
      <button class="btn" type="button" @click="run(() => post('/api/cloud/sync'))"><i class="fas fa-sync-alt"></i>{{ t("Synchroniser maintenant") }}</button>
    </template>
  </section>

  <section v-if="icloud" class="card">
    <div class="card-head"><h2><i class="fab fa-apple"></i>{{ t("Albums partagés iCloud") }}</h2></div>
    <p class="small muted">{{ t("Sur l'iPhone : app Photos › album partagé › bouton Personnes › activez « Site web public », puis « Partager le lien ». Collez ce lien ici : aucun identifiant Apple n'est demandé.") }}</p>
    <form class="row" @submit.prevent="addAlbum">
      <input v-model="icloudUrl" type="url" class="spacer" placeholder="https://www.icloud.com/sharedalbum/#B0…">
      <button class="btn primary" type="submit"><i class="fas fa-plus"></i>{{ t("Ajouter l'album") }}</button></form>
    <ul class="list"><li v-for="a in icloud.albums" :key="a.token"><span class="spacer">{{ a.name }} ({{ a.count }} {{ t("éléments") }})</span>
      <button class="btn small" type="button" @click="icloudSet({ remove: a.token })">{{ t("Retirer") }}</button></li></ul>
    <label class="check"><input type="checkbox" :checked="icloud.auto" @change="icloudSet({ auto: ($event.target as HTMLInputElement).checked })">{{ t("Synchroniser automatiquement (toutes les heures)") }}</label>
    <button v-if="icloud.albums.length" class="btn" type="button" @click="run(() => post('/api/icloud/sync'))"><i class="fas fa-sync-alt"></i>{{ t("Synchroniser maintenant") }}</button>
  </section>

  <section v-if="boot.admin" class="card">
    <div class="card-head"><h2><i class="fas fa-envelope"></i>{{ t("Photos par e-mail") }}</h2></div>
    <p class="small muted">{{ t("Donnez au cadre sa propre adresse e-mail (par exemple une adresse Gmail créée pour lui) : la famille y envoie ses photos en pièce jointe et elles s'affichent toutes seules. L'objet du message devient la légende.") }}</p>
    <label class="check"><input v-model="mail.enabled" type="checkbox" class="switch" @change="saveMail">{{ t("Relever la boîte mail (toutes les 5 minutes)") }}</label>
    <div class="mail">
      <label class="field">{{ t("Adresse du cadre") }}<input v-model="mail.user" type="email" autocomplete="off" placeholder="cadre.famille@gmail.com" @change="guessHost"></label>
      <label class="field">{{ t("Mot de passe d'application") }}<input v-model="mail.password" type="password" autocomplete="new-password" :placeholder="mail.has_password ? t('Mot de passe enregistré (laisser vide pour le garder)') : ''"></label>
      <label class="field">{{ t("Serveur IMAP") }}<input v-model="mail.host" type="text" placeholder="imap.gmail.com"></label>
      <label class="field">Port<input v-model.number="mail.port" type="number" min="1" max="65535"></label>
      <label class="field">{{ t("Dossier") }}<input v-model="mail.folder" type="text"></label>
      <label class="field">{{ t("Photos des autres expéditeurs :") }}
        <select v-model="mail.unknown"><option value="pending">{{ t("À valider (comme les photos d'invités)") }}</option><option value="ignore">{{ t("Ignorées") }}</option></select></label>
    </div>
    <label class="field">{{ t("Expéditeurs de confiance (affichés directement)") }}<textarea v-model="mail.allowed" rows="2" placeholder="mamie@orange.fr, papa@gmail.com"></textarea></label>
    <p class="small muted">{{ t("Gmail : activez la validation en deux étapes, puis créez un mot de passe d'application sur myaccount.google.com/apppasswords. Votre mot de passe habituel ne fonctionnera pas.") }}</p>
    <div class="row">
      <button class="btn primary" type="button" @click="saveMail">{{ t("Enregistrer") }}</button>
      <button class="btn" type="button" @click="testMail">{{ t("Tester la connexion") }}</button>
      <button class="btn" type="button" @click="run(() => post('/api/email/check'))"><i class="fas fa-inbox"></i>{{ t("Relever maintenant") }}</button>
    </div>
  </section>

  <section v-if="denied.length" class="card">
    <div class="card-head"><h2><i class="fas fa-exclamation-triangle"></i>{{ t("Photos que le cadre ne peut pas retirer du Drive") }}</h2></div>
    <ul class="list"><li v-for="f in denied" :key="f.remote_path"><span class="spacer">{{ f.remote_path }}<template v-if="!f.local"> {{ t("(plus sur le cadre)") }}</template></span>
      <a v-if="f.drive_url" :href="f.drive_url" target="_blank" rel="noopener">{{ t("Ouvrir dans Drive") }}</a></li></ul>
    <button class="btn" type="button" @click="run(() => post('/api/gdrive/denied/retry')).then(loadDenied)"><i class="fas fa-redo"></i>{{ t("Réessayer à la prochaine synchronisation") }}</button>
  </section>
</template>

<style scoped>
.card { margin-top: 1rem; }
.field { display: grid; gap: .25rem; font-weight: 600; font-size: .9rem; }
input[type="text"], input[type="url"], input[type="email"], input[type="password"], input[type="number"], select, textarea {
  font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; min-width: 0; }
textarea { width: 100%; }
.check { display: flex; align-items: center; gap: .5rem; margin: .4rem 0; }
.steps { display: grid; gap: .6rem; padding-left: 1.2rem; }
h3 { font-size: 1rem; margin: 1rem 0 .4rem; }
.folders { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: .2rem; max-height: 260px; overflow: auto; }
.list { list-style: none; padding: 0; margin: .6rem 0; }
.list li { display: flex; gap: .5rem; align-items: center; padding: .35rem 0; border-bottom: 1px solid var(--border); }
.mail { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .6rem; margin: .6rem 0; }
.btn.small { padding: .25rem .7rem; font-size: .8rem; }
code { background: var(--surface-2); padding: .1rem .4rem; border-radius: 6px; }
</style>
