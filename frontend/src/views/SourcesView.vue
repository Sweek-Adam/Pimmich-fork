<script setup lang="ts">
import { onMounted, ref } from "vue";
import SettingsPage from "../components/SettingsPage.vue";
import CloudCards from "../components/sources/CloudCards.vue";
import GdriveCard from "../components/sources/GdriveCard.vue";
import PeopleCard from "../components/sources/PeopleCard.vue";
import QualityCard from "../components/sources/QualityCard.vue";
import { get, post } from "../api";
import { boot } from "../boot";
import { t } from "../i18n";
import { values, type Section } from "../settings";
import { run } from "../toast";

const choices = ref<{ key: string; label: string }[]>([]);
const selected = ref<string[]>([]);

const sections: Section[] = [
  { title: () => t("Configuration de l'album photo Immich"), icon: "fa-images", fields: [
    { key: "immich_url", label: () => t("URL du serveur Immich :"), type: "text", placeholder: "http://192.168.1.10:2283" },
    ...(boot.admin ? [{ key: "immich_token", label: () => t("Token d'accès Immich :"), type: "secret" as const }] : []),
    { key: "album_name", label: () => t("Nom technique de l'album Immich :"), type: "text" },
    { key: "immich_max_photos", label: () => t("Limite de photos à télécharger (Immich)"), type: "number", min: 0, max: 100000, help: () => t("0 = sans limite.") },
    { key: "random_content_in_album", label: () => t("Récupération aléatoire des images dans l'album (Immich)"), type: "toggle" },
    { key: "immich_auto_update", label: () => t("Activer la mise à jour automatique"), type: "toggle" },
    { key: "immich_update_interval_hours", label: () => t("Intervalle de mise à jour (heures):"), type: "number", min: 1, max: 720, showIf: (v) => !!v.immich_auto_update },
  ] },
  { title: () => t("Configuration du partage Samba (Windows)"), icon: "fa-network-wired", fields: [
    { key: "smb_host", label: () => t("Serveur :"), type: "text", placeholder: t("ex: 192.168.1.50 ou MON-NAS") },
    { key: "smb_share", label: () => t("Nom du partage :"), type: "text", placeholder: t("ex: Photos") },
    { key: "smb_path", label: () => t("Chemin dans le partage (optionnel) :"), type: "text", placeholder: t("ex: Famille/2024") },
    { key: "smb_user", label: () => t("Nom d'utilisateur (optionnel) :"), type: "text" },
    ...(boot.admin ? [{ key: "smb_password", label: () => t("Mot de passe (optionnel) :"), type: "secret" as const }] : []),
    { key: "smb_auto_update", label: () => t("Activer la mise à jour automatique"), type: "toggle" },
    { key: "smb_update_interval_hours", label: () => t("Intervalle de mise à jour (heures):"), type: "number", min: 1, max: 720, showIf: (v) => !!v.smb_auto_update },
  ] },
  { title: () => t("Options de démarrage"), icon: "fa-play", fields: [
    { key: "skip_initial_auto_import", label: () => t("Ignorer le premier import automatique au démarrage"), type: "toggle",
      help: () => t("Si cette option est cochée, les mises à jour automatiques (Immich, Samba) ne se lanceront pas immédiatement après un redémarrage du cadre, mais attendront le prochain cycle programmé.") },
    { key: "hide_duplicates", label: () => t("Masquer les photos en double entre les sources"), type: "toggle",
      help: () => t("Une même photo reçue par plusieurs sources (ex. Google Drive et Telegram) n'est affichée qu'une fois, de préférence celle mise en favori.") },
  ] },
];

async function loadSources() {
  const d = await get<{ selected: string[]; choices: { key: string; label: string }[] }>("/api/display_sources");
  choices.value = d.choices;
  selected.value = d.selected;
}
async function toggleSource(key: string) {
  selected.value = selected.value.includes(key) ? selected.value.filter((s) => s !== key) : [...selected.value, key];
  await run(() => post("/api/display_sources", { selected: selected.value }));
}
async function testSamba() {
  await run(() => post("/test-samba", { smb_host: values.smb_host, smb_share: values.smb_share, smb_path: values.smb_path, smb_user: values.smb_user }));
}

onMounted(() => loadSources().catch(() => {}));
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fas fa-layer-group"></i>{{ t("Sources à afficher dans le diaporama") }}</h2></div>
    <p class="small muted">{{ t("Sélectionnez les sources de photos à inclure dans le diaporama. Les photos seront mélangées entre les sources sélectionnées.") }}</p>
    <div class="sources">
      <label v-for="c in choices" :key="c.key" class="source" :class="{ on: selected.includes(c.key) }">
        <input type="checkbox" :checked="selected.includes(c.key)" @change="toggleSource(c.key)">{{ c.label }}</label>
    </div>
  </section>
  <SettingsPage :sections="sections">
    <div class="row samba"><button class="btn" type="button" @click="testSamba"><i class="fas fa-plug"></i>{{ t("Tester la connexion Samba") }}</button></div>
    <GdriveCard class="block" />
    <PeopleCard class="block" />
    <QualityCard class="block" />
    <CloudCards />
  </SettingsPage>
</template>

<style scoped>
.sources { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: .4rem; margin-top: .7rem; margin-bottom: 1rem; }
.source { display: flex; align-items: center; gap: .5rem; padding: .5rem .7rem; border: 1px solid var(--border); border-radius: 10px; cursor: pointer; }
.source.on { border-color: var(--accent); background: var(--accent-soft); }
.samba { margin-top: .6rem; }
.block { margin-top: 1rem; }
</style>
