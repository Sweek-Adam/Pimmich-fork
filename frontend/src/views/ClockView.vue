<script setup lang="ts">
import { onMounted, ref } from "vue";
import AgendaCard from "../components/AgendaCard.vue";
import SettingsPage from "../components/SettingsPage.vue";
import TidesCard from "../components/TidesCard.vue";
import { get } from "../api";
import { t } from "../i18n";
import type { Section } from "../settings";

const fonts = ref<{ value: string; label: string }[]>([]);
onMounted(() => get<{ fonts: { value: string; label: string }[] }>("/api/settings/fonts").then((d) => (fonts.value = d.fonts)).catch(() => {}));

const clock = (v: Record<string, unknown>) => !!v.show_clock;
const tides = (v: Record<string, unknown>) => !!v.show_tides;
const sections: Section[] = [
  { title: () => t("Affichage de l'heure"), icon: "fa-clock", fields: [
    { key: "show_clock", label: () => t("Afficher l'heure"), type: "toggle" },
    { key: "clock_position", label: () => t("Position de l'heure :"), type: "select", showIf: clock,
      options: () => [{ value: "left", label: t("Gauche") }, { value: "center", label: t("Centre") }, { value: "right", label: t("Droite") }] },
    { key: "clock_format", label: () => t("Format de l'heure"), type: "select", showIf: clock,
      options: () => [{ value: "%H:%M", label: "14:05" }, { value: "%H:%M:%S", label: "14:05:09" }, { value: "%I:%M %p", label: "02:05 PM" }] },
    { key: "clock_layout", label: () => t("Disposition"), type: "select", showIf: clock,
      options: () => [{ value: "line", label: t("Tout sur une ligne") }, { value: "stacked", label: t("L'heure en grand, la date et la météo en dessous") }] },
    { key: "clock_second_line_percent", label: () => t("Taille de la date et de la météo"), type: "range", min: 30, max: 100, step: 5, unit: " %",
      showIf: (v) => clock(v) && v.clock_layout === "stacked" },
    { key: "clock_font_path", label: () => t("Police :"), type: "select", showIf: (v) => clock(v) && fonts.value.length > 0, options: () => fonts.value },
    { key: "clock_font_size", label: () => t("Taille de la police :"), type: "number", min: 12, max: 400, showIf: clock,
      help: () => t("Si la ligne est trop longue pour l'écran, elle est réduite automatiquement.") },
    { key: "clock_offset_x", label: () => t("Décalage horizontal (px)"), type: "number", min: -2000, max: 2000, showIf: clock },
    { key: "clock_offset_y", label: () => t("Décalage vertical (px)"), type: "number", min: -2000, max: 2000, showIf: clock },
    { key: "clock_color", label: () => t("Couleur du texte (hex) :"), type: "color", showIf: clock },
    { key: "clock_outline_color", label: () => t("Couleur du contour (hex) :"), type: "color", showIf: clock },
    { key: "clock_background_enabled", label: () => t("Afficher un fond derrière l'heure/date/météo"), type: "toggle", showIf: clock },
    { key: "clock_background_style", label: () => t("Forme du fond"), type: "select", showIf: (v) => clock(v) && !!v.clock_background_enabled,
      options: () => [{ value: "band", label: t("Bandeau sur toute la largeur") }, { value: "box", label: t("Cadre arrondi autour du texte") }] },
    { key: "clock_background_color", label: () => t("Couleur du fond"), type: "color", showIf: (v) => clock(v) && !!v.clock_background_enabled,
      help: () => t("8 chiffres pour la transparence : #00000080 = noir à moitié transparent.") },
  ] },
  { title: () => t("Affichage de la date"), icon: "fa-calendar-alt", fields: [
    { key: "show_date", label: () => t("Afficher la date (sous l'heure)"), type: "toggle" },
    { key: "date_format", label: () => t("Format de la date :"), type: "text", placeholder: "%A %d %B %Y", showIf: (v) => !!v.show_date,
      help: () => t("%A : jour, %d : jour du mois, %B : mois, %Y : année.") },
  ] },
  { title: () => t("Affichage de la météo (OpenWeatherMap)"), icon: "fa-cloud-sun", fields: [
    { key: "show_weather", label: () => t("Afficher la météo"), type: "toggle" },
    { key: "weather_city", label: () => t("Ville :"), type: "text", placeholder: "Paris" },
    { key: "weather_api_key", label: () => t("Clé API :"), type: "secret" },
    { key: "weather_units", label: () => t("Unités :"), type: "select",
      options: () => [{ value: "metric", label: t("Celsius") }, { value: "imperial", label: t("Fahrenheit") }] },
    { key: "weather_update_interval_minutes", label: () => t("Mise à jour de la météo (minutes)"), type: "number", min: 10, max: 1440 },
    { key: "show_sun_moon", label: () => t("Afficher le lever et le coucher du soleil, et la lune"), type: "toggle" },
    { key: "weather_animation", label: () => t("Pluie et neige animées :"), type: "select",
      help: () => t("Quand il pleut, neige ou fait de l'orage dehors, quelques gouttes, flocons ou éclairs passent sur la photo."),
      options: () => [{ value: "start", label: t("Au début de chaque photo (8 s)") }, { value: "always", label: t("Pendant toute la photo") }, { value: "off", label: t("Jamais") }] },
  ] },
  { title: () => t("Affichage des marées (StormGlass Tide API)"), icon: "fa-water",
    intro: () => t("Les heures de pleine et basse mer s'affichent en bas de l'écran. Il faut une clé API StormGlass (gratuite sur stormglass.io) et les coordonnées du port, par exemple trouvées sur latlong.net."),
    fields: [
    { key: "show_tides", label: () => t("Afficher les informations de marée"), type: "toggle" },
    { key: "tide_latitude", label: () => t("Latitude (ex: 48.3904) :"), type: "text", placeholder: "48.3904" },
    { key: "tide_longitude", label: () => t("Longitude (ex: -4.4861) :"), type: "text", placeholder: "-4.4861" },
    { key: "stormglass_api_key", label: () => t("Clé API StormGlass :"), type: "secret" },
    { key: "tide_offset_x", label: () => t("Décalage horizontal (px)"), type: "number", min: -2000, max: 2000, showIf: tides },
    { key: "tide_offset_y", label: () => t("Décalage vertical (px)"), type: "number", min: -2000, max: 2000, showIf: tides },
  ] },
];
</script>

<template>
  <SettingsPage :sections="sections">
    <AgendaCard />
    <TidesCard />
  </SettingsPage>
</template>
