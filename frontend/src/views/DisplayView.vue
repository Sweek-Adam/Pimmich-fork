<script setup lang="ts">
import SettingsPage from "../components/SettingsPage.vue";
import { t } from "../i18n";
import type { Section } from "../settings";

const transitions = () => [
  ["fade", t("Fondu enchaîné")], ["fade_black", t("Fondu au noir")], ["zoom", t("Zoom en fondu")],
  ["slide_left", t("Glisser depuis la gauche")], ["slide_right", t("Glisser depuis la droite")],
  ["slide_up", t("Glisser depuis le bas")], ["slide_down", t("Glisser depuis le haut")],
  ["push_left", t("Pousser vers la gauche")], ["push_up", t("Pousser vers le haut")], ["wipe", t("Rideau")],
  ["blinds", t("Stores")], ["iris", t("Iris (cercle qui s'ouvre)")], ["random", t("Au hasard (une différente à chaque photo)")],
].map(([value, label]) => ({ value, label }));

const sections: Section[] = [
  { title: () => t("Paramètres d'affichage"), icon: "fa-desktop", fields: [
    { key: "display_duration", label: () => t("Durée d'affichage (en secondes) :"), type: "number", min: 3, max: 3600 },
  ] },
  { title: () => t("Horaires Semaine (Lun-Ven)"), icon: "fa-calendar-week", fields: [
    { key: "active_start_weekday", label: () => t("Allumage :"), type: "time" },
    { key: "active_end_weekday", label: () => t("Extinction :"), type: "time" },
  ] },
  { title: () => t("Horaires Weekend (Sam-Dim)"), icon: "fa-calendar-day", fields: [
    { key: "active_start_weekend", label: () => t("Allumage :"), type: "time" },
    { key: "active_end_weekend", label: () => t("Extinction :"), type: "time" },
  ] },
  { title: () => t("Le soir et la nuit"), icon: "fa-moon", fields: [
    { key: "dim_enabled", label: () => t("Baisser la luminosité le soir"), type: "toggle", help: () => t("La baisse se fait en douceur (45 minutes) et dure jusqu'au matin.") },
    { key: "dim_start", label: () => t("À partir de :"), type: "timeOrSunset", showIf: (v) => !!v.dim_enabled,
      options: () => [{ value: "time", label: t("Une heure précise") }, { value: "sunset", label: t("Le coucher du soleil") }] },
    { key: "dim_level", label: () => t("Luminosité du soir :"), type: "range", min: 10, max: 90, step: 5, unit: " %", showIf: (v) => !!v.dim_enabled },
    { key: "night_mode", label: () => t("En dehors des heures d'affichage :"), type: "select",
      options: () => [{ value: "off", label: t("Écran éteint") }, { value: "clock", label: t("Horloge de nuit (l'heure seule, en couleur douce)") }] },
    { key: "night_brightness", label: () => t("Luminosité :"), type: "range", min: 5, max: 100, step: 5, unit: " %", showIf: (v) => v.night_mode === "clock" },
    { key: "night_color", label: () => t("Couleur :"), type: "select", showIf: (v) => v.night_mode === "clock",
      options: () => [{ value: "amber", label: t("Ambre") }, { value: "red", label: t("Rouge") }, { value: "white", label: t("Blanc") }, { value: "blue", label: t("Bleu") }] },
    { key: "night_show_date", label: () => t("Afficher la date"), type: "toggle", showIf: (v) => v.night_mode === "clock" },
  ] },
  { title: () => t("Transitions et mouvement"), icon: "fa-film", fields: [
    { key: "transition_enabled", label: () => t("Activer l'effet de transition entre les photos"), type: "toggle" },
    { key: "transition_type", label: () => t("Type de transition :"), type: "select", options: transitions, showIf: (v) => !!v.transition_enabled },
    { key: "transition_duration", label: () => t("Durée de transition (secondes) :"), type: "number", min: 0, max: 10, step: 0.1, showIf: (v) => !!v.transition_enabled },
    { key: "beat_sync", label: () => t("Caler le rythme sur la musique de fond (changement de photo sur le temps)"), type: "toggle" },
    { key: "transition_fps", label: () => t("Fréquence d'images (FPS) :"), type: "select",
      options: () => [{ value: "auto", label: t("Automatique (30 FPS sur Pi 3, 60 FPS sinon)") }, { value: "30", label: "30 FPS" }, { value: "60", label: "60 FPS" }] },
    { key: "pan_zoom_enabled", label: () => t("Activer l'effet Pan/Zoom sur les photos"), type: "toggle" },
    { key: "pan_zoom_factor", label: () => t("Amplitude du zoom"), type: "number", min: 1, max: 2, step: 0.05, showIf: (v) => !!v.pan_zoom_enabled },
  ] },
  { title: () => t("Ce jour-là"), icon: "fa-history",
    intro: () => t("Les photos prises un jour comme aujourd'hui, les années précédentes (toutes les sources : date de l'appareil photo, ou du nom du fichier pour WhatsApp et les téléphones)."),
    fields: [
      { key: "memories_banner", label: () => t("Ruban « Il y a 5 ans » sur ces photos"), type: "toggle" },
      { key: "memories_composition", label: () => t("Composition « Ce jour-là » (une photo par année)"), type: "toggle" },
      { key: "memories_every_minutes", label: () => t("Toutes les (minutes)"), type: "number", min: 1, max: 1440, showIf: (v) => !!v.memories_composition },
      { key: "anniversary_boost_enabled", label: () => t("Activer le boost pour les photos à leur date anniversaire de prise de vue"), type: "toggle" },
      { key: "anniversary_boost_factor", label: () => t("Facteur de boost anniversaire :"), type: "number", min: 0, max: 20, showIf: (v) => !!v.anniversary_boost_enabled },
      { key: "favorite_boost_factor", label: () => t("Fréquence des favoris (nombre d'ajouts supplémentaires dans la liste de lecture) :"), type: "number", min: 0, max: 20,
        help: () => t("Ex: 0 = pas de boost, 2 = 3x plus de chances d'apparaître.") },
    ] },
  { title: () => t("Agenda « Cette semaine »"), icon: "fa-calendar-check",
    intro: () => t("Les événements des 7 prochains jours et vos comptes à rebours (réglés dans Horloge & météo)."),
    fields: [
      { key: "agenda_slide", label: () => t("Afficher la diapositive « Cette semaine »"), type: "toggle" },
      { key: "agenda_every_minutes", label: () => t("Toutes les (minutes)"), type: "number", min: 1, max: 1440, showIf: (v) => !!v.agenda_slide },
    ] },
  { title: () => t("Vidéos"), icon: "fa-video", fields: [
    { key: "slideshow_video_enabled", label: () => t("Afficher les vidéos dans le diaporama"), type: "toggle" },
    { key: "video_audio_enabled", label: () => t("Activer le son pour les vidéos"), type: "toggle", showIf: (v) => !!v.slideshow_video_enabled },
    { key: "video_audio_output", label: () => t("Sortie audio :"), type: "select", showIf: (v) => !!v.slideshow_video_enabled && !!v.video_audio_enabled,
      options: () => [{ value: "auto", label: t("Automatique") }, { value: "hdmi", label: t("HDMI") }, { value: "jack", label: t("Jack 3.5mm (Casque)") }] },
    { key: "video_audio_volume", label: () => t("Volume :"), type: "range", min: 0, max: 100, step: 5, unit: " %", showIf: (v) => !!v.slideshow_video_enabled && !!v.video_audio_enabled },
    { key: "music_duck_videos", label: () => t("Baisser la musique pendant les vidéos (elle revient ensuite)"), type: "toggle" },
    { key: "video_hwdec_enabled", label: () => t("Activer le décodage vidéo matériel (plus fluide, mais peut être instable)"), type: "toggle",
      help: () => t("Cochez cette case pour une lecture plus fluide sur les Raspberry Pi. Décochez si vous rencontrez des écrans bleus/noirs après les vidéos.") },
  ] },
  { title: () => t("Télévision"), icon: "fa-tv", fields: [
    { key: "cec_enabled", label: () => t("Piloter la télévision par HDMI-CEC"), type: "toggle",
      help: () => t("Avec une TV : elle s'allume sur l'entrée du cadre au réveil et se met en veille avec lui. Activez aussi « HDMI-CEC » (Anynet+, Bravia Sync, SimpLink...) dans les réglages de la TV.") },
  ] },
];
</script>

<template>
  <SettingsPage :sections="sections" classic-tab="tab-affichage"
                :classic-hint="() => t('Orientation, résolution, Home Assistant, prise connectée et réveil à l\'arrivée : interface classique')" />
</template>
