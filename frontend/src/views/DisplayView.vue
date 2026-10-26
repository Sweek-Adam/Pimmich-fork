<script setup lang="ts">
import ButtonCard from "../components/ButtonCard.vue";
import HomeAssistantCard from "../components/HomeAssistantCard.vue";
import PresenceCard from "../components/PresenceCard.vue";
import MotionCard from "../components/MotionCard.vue";
import ScreenCard from "../components/ScreenCard.vue";
import SettingsPage from "../components/SettingsPage.vue";
import SmartPlugCard from "../components/SmartPlugCard.vue";
import { boot } from "../boot";
import { t } from "../i18n";
import type { Section } from "../settings";

const plug = (v: Record<string, unknown>) => !!v.smart_plug_enabled;
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
  { title: () => t("Écran"), icon: "fa-sync-alt", fields: [
    { key: "screen_orientation", label: () => t("Orientation du cadre"), type: "select",
      help: () => t("L'écran pivote tout seul et les photos sont repréparées en arrière-plan aux nouvelles dimensions (le diaporama continue pendant ce temps)."),
      options: () => [{ value: "landscape", label: t("Paysage (Horizontal)") }, { value: "portrait", label: t("Portrait (Vertical)") },
        { value: "landscape_flipped", label: t("Paysage retourné") }, { value: "portrait_flipped", label: t("Portrait retourné") },
        { value: "auto", label: t("Automatique (capteur d'orientation)") }] },
    { key: "display_width", label: () => t("Largeur d'affichage cible (px) :"), type: "number", min: 240, max: 7680 },
    { key: "display_height", label: () => t("Hauteur d'affichage cible (px) :"), type: "number", min: 240, max: 7680 },
    { key: "display_backend", label: () => t("Mode d'affichage du diaporama"), type: "select",
      help: () => t("Wayland natif : environ 85 Mo de mémoire en moins (Xwayland n'est plus nécessaire). Le changement prend effet au prochain démarrage du Raspberry Pi."),
      options: () => [{ value: "x11", label: t("X11 (via Xwayland, éprouvé)") }, { value: "wayland", label: t("Wayland natif (plus léger)") }] },
    { key: "screen_height_percent", label: () => t("Hauteur utile de l'écran"), type: "range", min: 10, max: 100, step: 1, unit: " %",
      help: () => t("Pour un écran dont le bas est caché par le cadre : les photos n'occupent que cette partie de la hauteur.") },
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
    { key: "pan_zoom_style", label: () => t("Mouvement"), type: "select", showIf: (v) => !!v.pan_zoom_enabled,
      options: () => [{ value: "kenburns", label: t("Ken Burns : zoom lent vers les visages") }, { value: "pan", label: t("Glissement d'un bord à l'autre") }] },
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
      { key: "forgotten_boost_enabled", label: () => t("Faire revenir les photos oubliées (jamais ou rarement montrées)"), type: "toggle",
        help: () => t("Le cadre compte les passages de chaque photo : celles qui ne sont jamais passées, ou parmi les moins vues, reviennent plus souvent.") },
      { key: "forgotten_boost_factor", label: () => t("Passages en plus pour une photo jamais montrée"), type: "number", min: 1, max: 10, showIf: (v) => !!v.forgotten_boost_enabled },
    ] },
  { title: () => t("Agenda « Cette semaine »"), icon: "fa-calendar-check",
    intro: () => t("Les événements des 7 prochains jours et vos comptes à rebours (réglés dans Horloge & météo)."),
    fields: [
      { key: "agenda_slide", label: () => t("Afficher la diapositive « Cette semaine »"), type: "toggle" },
      { key: "agenda_every_minutes", label: () => t("Toutes les (minutes)"), type: "number", min: 1, max: 1440, showIf: (v) => !!v.agenda_slide },
    ] },
  { title: () => t("« Votre semaine sur le cadre »"), icon: "fa-calendar-week",
    intro: () => t("Le dimanche soir (à partir de 17 h), une diapositive résume la semaine : les nouvelles photos et qui les a envoyées, les messages et les cœurs envoyés depuis les téléphones."),
    fields: [
      { key: "weekly_recap_slide", label: () => t("Afficher le résumé de la semaine"), type: "toggle" },
      { key: "weekly_recap_every_minutes", label: () => t("Toutes les (minutes)"), type: "number", min: 1, max: 1440, showIf: (v) => !!v.weekly_recap_slide },
    ] },
  { title: () => t("Langue"), icon: "fa-language", fields: [
    { key: "language", label: () => t("Langue des textes affichés sur le cadre"), type: "select",
      options: () => [{ value: "fr", label: "Français" }, { value: "en", label: "English" }, { value: "es", label: "Español" }, { value: "de", label: "Deutsch" }, { value: "ja", label: "日本語" }],
      help: () => t("Date, jeux, mode fête, compositions, citations... L'interface d'administration suit la langue de votre navigateur.") },
  ] },
  { title: () => t("Vidéos"), icon: "fa-video", fields: [
    { key: "slideshow_video_enabled", label: () => t("Afficher les vidéos dans le diaporama"), type: "toggle" },
    { key: "video_audio_enabled", label: () => t("Activer le son pour les vidéos"), type: "toggle", showIf: (v) => !!v.slideshow_video_enabled },
    { key: "video_audio_output", label: () => t("Sortie audio :"), type: "select", showIf: (v) => !!v.slideshow_video_enabled && !!v.video_audio_enabled,
      options: () => [{ value: "auto", label: t("Automatique") }, { value: "hdmi", label: t("HDMI") }, { value: "jack", label: t("Jack 3.5mm (Casque)") }] },
    { key: "video_audio_volume", label: () => t("Volume :"), type: "range", min: 0, max: 100, step: 5, unit: " %", showIf: (v) => !!v.slideshow_video_enabled && !!v.video_audio_enabled },
    { key: "music_duck_videos", label: () => t("Baisser la musique pendant les vidéos (elle revient ensuite)"), type: "toggle" },
    { key: "motion_photos_enabled", label: () => t("Animer les photos animées des téléphones"), type: "toggle",
      help: () => t("Photos animées Samsung et Google, Live Photos d'iPhone : leur courte vidéo est rejouée sur la photo, comme un GIF. Les animations sont créées la nuit (ou tout de suite depuis Préparation des médias).") },
    { key: "short_videos_in_layouts", label: () => t("Courtes vidéos dans les dispositions (en boucle, sans le son)"), type: "toggle",
      help: () => t("Une courte vidéo peut prendre place dans une composition, comme un GIF ; les autres vidéos restent seules à l'écran, avec le son.") },
    { key: "short_videos_max_seconds", label: () => t("Courte vidéo : au plus (secondes)"), type: "number", min: 2, max: 120, showIf: (v) => !!v.short_videos_in_layouts },
    { key: "heavy_videos_at_night", label: () => t("Préparer les grosses vidéos la nuit seulement"), type: "toggle",
      help: () => t("Pendant la journée, le cadre prépare d'abord les photos et les petites vidéos ; les grosses attendent que l'écran soit éteint (le Raspberry Pi reste fluide). Le bouton Préparer de la page Préparation des médias agit toujours tout de suite.") },
    { key: "video_night_above_mb", label: () => t("Grosse vidéo à partir de (Mo)"), type: "number", min: 0, max: 100000, showIf: (v) => !!v.heavy_videos_at_night },
    { key: "video_light_above_mb", label: () => t("Encodage allégé des vidéos à partir de (Mo)"), type: "number", min: 0, max: 100000,
      help: () => t("Les vidéos plus lourdes sont préparées en 720p (30 images/s au plus) : bien plus rapide et moins gourmand sur un Raspberry Pi, toujours en plein écran. 0 = jamais.") },
    { key: "video_excerpts_enabled", label: () => t("Longues vidéos : ne montrer que le passage le plus animé"), type: "toggle",
      help: () => t("Au lieu de toute la vidéo, le cadre en montre le meilleur moment (là où ça bouge le plus). La vidéo complète reste dans la bibliothèque.") },
    { key: "video_excerpt_seconds", label: () => t("Durée de l'extrait (secondes)"), type: "number", min: 5, max: 120, showIf: (v) => !!v.video_excerpts_enabled },
    { key: "video_excerpt_above_seconds", label: () => t("Pour les vidéos de plus de (secondes)"), type: "number", min: 20, max: 3600, showIf: (v) => !!v.video_excerpts_enabled },
    { key: "video_hwdec_enabled", label: () => t("Activer le décodage vidéo matériel (plus fluide, mais peut être instable)"), type: "toggle",
      help: () => t("Cochez cette case pour une lecture plus fluide sur les Raspberry Pi. Décochez si vous rencontrez des écrans bleus/noirs après les vidéos.") },
  ] },
  { title: () => t("Télévision"), icon: "fa-tv", fields: [
    { key: "cec_enabled", label: () => t("Piloter la télévision par HDMI-CEC"), type: "toggle",
      help: () => t("Avec une TV : elle s'allume sur l'entrée du cadre au réveil et se met en veille avec lui. Activez aussi « HDMI-CEC » (Anynet+, Bravia Sync, SimpLink...) dans les réglages de la TV.") },
    { key: "tv_remote_enabled", label: () => t("Piloter le cadre avec la télécommande de la TV"), type: "toggle",
      help: () => t("Quand la TV est sur l'entrée du cadre : ▶ / ◀ photo suivante ou précédente, OK pause, ▲ ou touche rouge ❤️ sur la photo, touche bleue « je pense à vous » vers les autres cadres de la famille, Stop ou Retour mise en veille ; n'importe quelle touche réveille le cadre. Nécessite le HDMI-CEC activé sur la TV.") },
  ] },
  { title: () => t("Gestion de l'alimentation (Prise Connectée)"), icon: "fa-plug",
    intro: () => t("Si votre écran ne se met pas complètement en veille, vous pouvez utiliser une prise connectée (Wi-Fi) pour couper son alimentation. Pimmich enverra une simple requête HTTP aux URLs que vous spécifiez."),
    fields: [
    { key: "smart_plug_enabled", label: () => t("Activer le contrôle par prise connectée"), type: "toggle" },
    { key: "smart_plug_on_url", label: () => t("URL pour ALLUMER la prise :"), type: "text", placeholder: "http://…", showIf: plug },
    { key: "smart_plug_off_url", label: () => t("URL pour ÉTEINDRE la prise :"), type: "text", placeholder: "http://…", showIf: plug },
    { key: "smart_plug_on_delay", label: () => t("Délai après allumage (secondes) :"), type: "number", min: 0, max: 30, showIf: plug,
      help: () => t("Temps d'attente pour que l'écran s'initialise avant de forcer la résolution. Augmentez si la résolution est toujours incorrecte.") },
    { key: "smart_plug_status_url", label: () => t("URL de Statut (Optionnel) :"), type: "text", placeholder: "http://…", showIf: plug },
    { key: "home_assistant_token", label: () => t("Token d'accès Home Assistant (si URL de statut HA) :"), type: "secret", showIf: plug,
      help: () => t("Créez un \"Token d'accès longue durée\" dans votre profil Home Assistant.") },
  ] },
  { title: () => t("Bouton physique"), icon: "fa-dot-circle",
    intro: () => t("Un bouton branché sur le Raspberry Pi : un appui met le cadre en veille, un autre le réveille."),
    fields: [
    { key: "button_enabled", label: () => t("Activer le bouton physique"), type: "toggle" },
    { key: "button_pin", label: () => t("Broche GPIO (numérotation BCM)"), type: "number", min: 2, max: 27, showIf: (v) => !!v.button_enabled },
  ] },
  { title: () => t("Détecteur de mouvement"), icon: "fa-walking",
    intro: () => t("Un petit capteur infrarouge (PIR) branché sur le Raspberry Pi : l'écran s'éteint quand personne n'est passé devant le cadre depuis un moment, et se rallume dès que quelqu'un entre dans la pièce."),
    fields: [
    { key: "motion_sensor_enabled", label: () => t("Activer le détecteur de mouvement"), type: "toggle" },
    { key: "motion_sensor_pin", label: () => t("Broche GPIO (numérotation BCM)"), type: "number", min: 2, max: 27, showIf: (v) => !!v.motion_sensor_enabled },
    { key: "motion_sleep_minutes", label: () => t("Éteindre l'écran après (minutes sans personne)"), type: "number", min: 1, max: 240, showIf: (v) => !!v.motion_sensor_enabled },
  ] },
];
</script>

<template>
  <SettingsPage :sections="sections">
    <div class="extra">
      <ScreenCard />
      <SmartPlugCard />
      <ButtonCard />
      <MotionCard />
      <PresenceCard />
      <HomeAssistantCard v-if="boot.admin" />
    </div>
  </SettingsPage>
</template>

<style scoped>
.extra { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr)); gap: 0 1rem; align-items: start; }
</style>
