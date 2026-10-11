<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import SettingField from "../SettingField.vue";
import { get, post } from "../../api";
import { boot } from "../../boot";
import { t } from "../../i18n";
import { loaded, setValue, values, type Field } from "../../settings";
import { notify, run } from "../../toast";

interface Folder { id: string; name: string }
const remotes = ref<string[]>([]);
const serviceEmail = ref<string | null>(null);
const selected = ref<Folder[]>([]);
const available = ref<Folder[] | null>(null);
const key = ref("");
const listing = ref(false);
const chosen = computed(() => new Set(selected.value.map((f) => f.id)));
const shown = computed(() => {
  const all = [...(available.value ?? [])];
  for (const f of selected.value) if (!all.some((a) => a.id === f.id)) all.unshift(f);
  return all;
});
const useRclone = computed(() => values.gdrive_backend === "rclone" || (values.gdrive_backend === "auto" && remotes.value.length > 0));

const fields: Field[] = [
  { key: "gdrive_backend", label: () => t("Méthode de connexion :"), type: "select",
    options: () => [{ value: "auto", label: t("Automatique (rclone si configuré, sinon compte de service)") },
      { value: "rclone", label: t("rclone (compte Google déjà configuré sur le Raspberry Pi)") }, { value: "service_account", label: t("Compte de service Google") }] },
];
const syncFields: Field[] = [
  { key: "gdrive_recursive", label: () => t("Inclure les sous-dossiers"), type: "toggle" },
  { key: "gdrive_trash_after_import", label: () => t("Mettre les fichiers à la corbeille Google Drive après import"), type: "toggle" },
  { key: "gdrive_auto_update", label: () => t("Activer la mise à jour automatique"), type: "toggle" },
  { key: "gdrive_update_interval_minutes", label: () => t("Vérifier les nouveautés toutes les (minutes) :"), type: "number", min: 5, max: 10080, showIf: (v) => !!v.gdrive_auto_update,
    help: () => t("Le diaporama n'est relancé que si des photos ou vidéos ont été ajoutées ou supprimées.") },
];

async function load() {
  const d = await get<{ remotes: string[]; service_email: string | null; folders: Folder[] }>("/api/gdrive/setup");
  remotes.value = d.remotes; serviceEmail.value = d.service_email; selected.value = d.folders;
}
async function listFolders() {
  listing.value = true;
  try {
    available.value = (await post<{ folders: Folder[] }>("/api/gdrive/folders", { backend: values.gdrive_backend, remote: values.gdrive_rclone_remote, key: key.value })).folders;
  } catch (e) { notify((e as Error).message, true); }
  listing.value = false;
}
async function toggle(folder: Folder) {
  selected.value = chosen.value.has(folder.id) ? selected.value.filter((f) => f.id !== folder.id) : [...selected.value, folder];
  await run(() => post("/api/gdrive/selected_folders", { folders: selected.value }));
}
async function saveKey() {
  const d = await run(() => post<{ service_email: string; message: string }>("/api/gdrive/service_account", { key: key.value }));
  if (d) { serviceEmail.value = d.service_email; key.value = ""; }
}

onMounted(() => load().catch(() => {}));
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fab fa-google-drive"></i>{{ t("Configuration Google Drive") }}</h2></div>
    <template v-if="loaded">
      <SettingField v-for="f in fields" :key="f.key" :field="f" />
      <label v-if="useRclone" class="field">{{ t("Remote rclone :") }}
        <select :value="values.gdrive_rclone_remote" @change="setValue('gdrive_rclone_remote', ($event.target as HTMLSelectElement).value)">
          <option v-for="r in remotes" :key="r" :value="r">{{ r }}:</option></select>
        <small v-if="!remotes.length" class="muted">{{ t("Aucun remote rclone Google Drive trouvé. Pour en créer un, lancez « rclone config » sur le Raspberry Pi.") }}</small></label>
      <div v-else class="sa">
        <p class="small muted">{{ t("Créez un compte de service dans la console Google Cloud (API Google Drive activée), téléchargez sa clé JSON et collez-la ci-dessous. Partagez ensuite vos dossiers de photos avec l'adresse e-mail du compte de service.") }}</p>
        <p v-if="serviceEmail" class="small"><strong>{{ t("Compte de service configuré :") }}</strong> <code>{{ serviceEmail }}</code></p>
        <template v-if="boot.admin">
          <textarea v-model="key" rows="3" :placeholder="serviceEmail ? t('Laisser vide pour conserver la clé actuelle') : '{&quot;type&quot;: &quot;service_account&quot;, ...}'"></textarea>
          <button class="btn small" type="button" :disabled="!key.trim()" @click="saveKey">{{ t("Enregistrer") }}</button>
        </template>
      </div>
    </template>
    <h3>{{ t("Dossiers à afficher dans le diaporama :") }}</h3>
    <button class="btn" type="button" :disabled="listing" @click="listFolders"><i class="fas" :class="listing ? 'fa-spinner fa-spin' : 'fa-folder-open'"></i>{{ t("Afficher mes dossiers Google Drive") }}</button>
    <div class="folders">
      <label v-for="f in shown" :key="f.id" class="check"><input type="checkbox" :checked="chosen.has(f.id)" @change="toggle(f)">{{ f.name }}</label>
    </div>
    <p v-if="!shown.length" class="small muted">{{ t("Aucun dossier sélectionné. Cliquez sur « Afficher mes dossiers Google Drive ».") }}</p>
    <template v-if="loaded"><SettingField v-for="f in syncFields" :key="f.key" :field="f" /></template>
  </section>
</template>

<style scoped>
.field { display: grid; gap: .3rem; font-weight: 600; font-size: .9rem; padding: .7rem 0; }
select, textarea { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; }
textarea { width: 100%; font-family: ui-monospace, monospace; font-size: .8rem; }
.sa { display: grid; gap: .5rem; padding: .5rem 0; }
h3 { font-size: 1rem; margin: 1rem 0 .5rem; }
.folders { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: .3rem; margin: .6rem 0; max-height: 300px; overflow: auto; }
.check { display: flex; align-items: center; gap: .4rem; font-size: .9rem; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; width: fit-content; }
code { background: var(--surface-2); padding: .1rem .4rem; border-radius: 6px; word-break: break-all; }
</style>
