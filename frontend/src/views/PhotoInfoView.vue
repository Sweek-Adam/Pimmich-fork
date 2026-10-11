<script setup lang="ts">
import { ref } from "vue";
import CaptionEditor from "../components/CaptionEditor.vue";
import SettingsPage from "../components/SettingsPage.vue";
import { t } from "../i18n";
import type { Section } from "../settings";

const flag = (v: Record<string, unknown>) => !!v.show_country_flag;
const editing = ref(false);
const sections: Section[] = [
  { title: () => t("Date de prise de vue"), icon: "fa-calendar", fields: [
    { key: "show_photo_date", label: () => t("Afficher la date de prise de vue"), type: "toggle" },
    { key: "photo_date_format", label: () => t("Format de la date :"), type: "text", placeholder: "%d %B %Y", showIf: (v) => !!v.show_photo_date,
      help: () => t("%A : jour, %d : jour du mois, %B : mois, %Y : année.") },
  ] },
  { title: () => t("Lieu"), icon: "fa-map-marker-alt", fields: [
    { key: "show_photo_location", label: () => t("Afficher la localisation (ville/pays)"), type: "toggle" },
    { key: "photo_location_format", label: () => t("Format du lieu"), type: "select", showIf: (v) => !!v.show_photo_location,
      options: () => [{ value: "city_country", label: t("Ville, Pays") }, { value: "city", label: t("Ville uniquement") }, { value: "country", label: t("Pays uniquement") }] },
    { key: "geocode_enabled", label: () => t("Trouver le nom du lieu pour toutes les photos géolocalisées (Google Drive, téléphone...)"), type: "toggle",
      help: () => t("Les coordonnées GPS des photos (jamais les photos) sont envoyées à OpenStreetMap pour connaître la ville ; chaque lieu n'est demandé qu'une fois. Sans cette option, seules les photos Immich ont un lieu.") },
  ] },
  { title: () => t("Drapeau du pays"), icon: "fa-flag", fields: [
    { key: "show_country_flag", label: () => t("Afficher le drapeau du pays"), type: "toggle" },
    { key: "country_flag_size", label: () => t("Taille du drapeau"), type: "select", showIf: flag,
      options: () => ["128x96", "192x144", "256x192"].map((value) => ({ value, label: value })) },
    { key: "country_flag_opacity", label: () => t("Opacité du drapeau"), type: "range", min: 0, max: 1, step: 0.05, showIf: flag },
    { key: "country_flag_position", label: () => t("Position du drapeau"), type: "select", showIf: flag,
      options: () => [{ value: "top_right", label: t("En haut à droite") }, { value: "top_left", label: t("En haut à gauche") },
        { value: "bottom_right", label: t("En bas à droite") }, { value: "bottom_left", label: t("En bas à gauche") }] },
    { key: "country_flag_offset_x", label: () => t("Décalage horizontal (px)"), type: "number", min: -2000, max: 2000, showIf: flag },
    { key: "country_flag_offset_y", label: () => t("Décalage vertical (px)"), type: "number", min: -2000, max: 2000, showIf: flag },
  ] },
];
</script>

<template>
  <SettingsPage :sections="sections">
    <section class="card style">
      <div class="card-head"><h2><i class="fas fa-palette"></i>{{ t("Style du texte") }}</h2></div>
      <p class="small muted">{{ t("Police, couleurs, fond, contour, position : réglez-les dans l'éditeur de légendes, avec un aperçu.") }}</p>
      <button class="btn primary" type="button" @click="editing = true"><i class="fas fa-palette"></i>{{ t("Personnaliser le style") }}</button>
    </section>
  </SettingsPage>
  <CaptionEditor v-if="editing" scope="metadata" @close="editing = false" />
</template>

<style scoped>
.style { margin-top: 1rem; }
</style>
