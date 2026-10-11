<script setup lang="ts">
import SettingsPage from "../components/SettingsPage.vue";
import { t } from "../i18n";
import type { Section } from "../settings";

const clock = (v: Record<string, unknown>) => !!v.show_clock;
const sections: Section[] = [
  { title: () => t("Affichage de l'heure"), icon: "fa-clock", fields: [
    { key: "show_clock", label: () => t("Afficher l'heure"), type: "toggle" },
    { key: "clock_position", label: () => t("Position de l'heure :"), type: "select", showIf: clock,
      options: () => [{ value: "left", label: t("Gauche") }, { value: "center", label: t("Centre") }, { value: "right", label: t("Droite") }] },
    { key: "clock_font_size", label: () => t("Taille de la police :"), type: "number", min: 12, max: 400, showIf: clock },
    { key: "clock_offset_x", label: () => t("Décalage horizontal (px)"), type: "number", min: -2000, max: 2000, showIf: clock },
    { key: "clock_offset_y", label: () => t("Décalage vertical (px)"), type: "number", min: -2000, max: 2000, showIf: clock },
    { key: "clock_color", label: () => t("Couleur du texte (hex) :"), type: "color", showIf: clock },
    { key: "clock_outline_color", label: () => t("Couleur du contour (hex) :"), type: "color", showIf: clock },
    { key: "clock_background_enabled", label: () => t("Afficher un fond derrière l'heure/date/météo"), type: "toggle", showIf: clock },
    { key: "clock_background_color", label: () => t("Couleur du fond"), type: "color", showIf: (v) => clock(v) && !!v.clock_background_enabled },
  ] },
  { title: () => t("Affichage de la date"), icon: "fa-calendar-alt", fields: [
    { key: "show_date", label: () => t("Afficher la date (sous l'heure)"), type: "toggle" },
    { key: "date_format", label: () => t("Format de la date :"), type: "text", placeholder: "%A %d %B %Y", showIf: (v) => !!v.show_date,
      help: () => t("%A : jour, %d : jour du mois, %B : mois, %Y : année.") },
  ] },
  { title: () => t("Affichage de la météo (OpenWeatherMap)"), icon: "fa-cloud-sun", fields: [
    { key: "show_weather", label: () => t("Afficher la météo"), type: "toggle" },
    { key: "weather_city", label: () => t("Ville :"), type: "text", placeholder: "Paris" },
    { key: "weather_units", label: () => t("Unités :"), type: "select",
      options: () => [{ value: "metric", label: t("Celsius") }, { value: "imperial", label: t("Fahrenheit") }] },
    { key: "weather_update_interval_minutes", label: () => t("Mise à jour de la météo (minutes)"), type: "number", min: 10, max: 1440 },
    { key: "show_sun_moon", label: () => t("Afficher le lever et le coucher du soleil, et la lune"), type: "toggle" },
    { key: "weather_animation", label: () => t("Pluie et neige animées :"), type: "select",
      help: () => t("Quand il pleut, neige ou fait de l'orage dehors, quelques gouttes, flocons ou éclairs passent sur la photo."),
      options: () => [{ value: "start", label: t("Au début de chaque photo (8 s)") }, { value: "always", label: t("Pendant toute la photo") }, { value: "off", label: t("Jamais") }] },
  ] },
];
</script>

<template>
  <SettingsPage :sections="sections" classic-tab="tab-heure"
                :classic-hint="() => t('Clé API météo, police, marées, agenda et comptes à rebours : interface classique')" />
</template>
