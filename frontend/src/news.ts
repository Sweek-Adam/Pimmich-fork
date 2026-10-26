// Nouveautés du cadre (page « Nouveautés » et bandeau de l'accueil). Ajouter les plus récentes en tête.
import { t } from "./i18n";

export interface News { id: number; date: string; icon: string; title: () => string; text: () => string; route?: string }

export const NEWS: News[] = [
  { id: 27, date: "2026-10-26", icon: "fa-palette", title: () => t("Coloriser les photos noir et blanc"),
    text: () => t("Les vieilles photos noir et blanc retrouvent des couleurs, calculées sur le cadre (une copie, l'original ne change pas). À installer une fois dans Importer."), route: "/importer" },
  { id: 26, date: "2026-10-26", icon: "fa-magic", title: () => t("Légendes proposées automatiquement"),
    text: () => t("Une courte description et des mots-clés pour chaque photo, pour la recherche ; à adopter en un clic (Immich, ou Claude en option)."), route: "/legendes" },
  { id: 25, date: "2026-10-26", icon: "fa-broadcast-tower", title: () => t("Diffuser sur une télé"),
    text: () => t("Le diaporama ou le film de l'année sur une télé Chromecast, sans câble."), route: "/affichage" },
  { id: 24, date: "2026-10-26", icon: "fa-heart", title: () => t("Plus proches"),
    text: () => t("« Je pense à vous » fait s'envoler des cœurs sur les autres cadres ; commentaires des invités sur la photo affichée ; rappels d'anniversaire ; bilan du mois par e-mail."), route: "/invites" },
  { id: 23, date: "2026-10-26", icon: "fa-history", title: () => t("Photos oubliées et extraits vidéo"),
    text: () => t("Les photos rarement montrées reviennent plus souvent ; les longues vidéos n'en montrent que le passage le plus animé."), route: "/affichage" },
  { id: 22, date: "2026-10-26", icon: "fa-camera-retro", title: () => t("Scanner, souvenirs vocaux, Ken Burns"),
    text: () => t("Numérisez les tirages papier avec le téléphone, racontez une photo de vive voix, et laissez le cadre zoomer lentement vers les visages."), route: "/importer" },
  { id: 21, date: "2026-10-26", icon: "fa-book-open", title: () => t("Livre, calendrier et film de l'année"),
    text: () => t("Un livre photo prêt à imprimer, un calendrier avec les anniversaires et un petit film en musique, en bas de la bibliothèque."), route: "/bibliotheque" },
  { id: 20, date: "2026-10-26", icon: "fa-print", title: () => t("Photomaton et mur de cadres"),
    text: () => t("Pendant une fête, les invités impriment la photo affichée ; plusieurs cadres côte à côte montrent ensemble une grande photo."), route: "/invites" },
  { id: 19, date: "2026-10-26", icon: "fa-hand-holding-heart", title: () => t("Mode grands-parents"),
    text: () => t("Une page à très gros boutons pour le téléphone de ceux qui n'aiment pas les applications, ouverte par un QR code."), route: "/invites" },
  { id: 18, date: "2026-10-26", icon: "fa-tv", title: () => t("Télécommande de la télé et détecteur de mouvement"),
    text: () => t("Pilotez le cadre avec la télécommande de la télé (HDMI-CEC) ; avec un petit capteur, l'écran s'éteint quand personne n'est là."), route: "/affichage" },
  { id: 17, date: "2026-10-26", icon: "fa-envelope-open-text", title: () => t("Photo du jour par e-mail"),
    text: () => t("Pour les proches sans cadre : une photo par jour, un souvenir « ce jour-là » de préférence."), route: "/invites" },
  { id: 16, date: "2026-10-26", icon: "fa-save", title: () => t("Sauvegarde automatique chaque semaine"),
    text: () => t("Photos, réglages et messages copiés chaque semaine sur un disque USB ou un NAS, la nuit."), route: "/maintenance" },
  { id: 15, date: "2026-10-25", icon: "fa-laptop", title: () => t("Pimmich sur un ordinateur"),
    text: () => t("Édition « événement » pour un mariage ou une fête : Pimmich sur un Mac ou un PC, le diaporama sur une télé ou un vidéoprojecteur (voir EVENEMENT.md sur GitHub).") },
  { id: 14, date: "2026-10-25", icon: "fa-language", title: () => t("Le cadre parle votre langue"),
    text: () => t("Les textes affichés sur le cadre (jeux, fête, compositions) suivent la langue choisie dans Affichage."), route: "/affichage" },
  { id: 13, date: "2026-10-25", icon: "fa-dice", title: () => t("Menu Jeux"),
    text: () => t("Onze jeux de famille joués depuis les téléphones : lancez une partie, suivez-la en direct et réglez les temps."), route: "/jeux" },
  { id: 12, date: "2026-10-25", icon: "fa-search", title: () => t("Recherche par contenu"),
    text: () => t("Avec un serveur Immich : cherchez « plage », « chien »... dans la bibliothèque."), route: "/bibliotheque" },
  { id: 11, date: "2026-10-25", icon: "fa-glass-cheers", title: () => t("Mode fête"),
    text: () => t("Un grand QR code à l'écran : les photos des invités s'affichent tout de suite, puis dans le Mur de la fête."), route: "/invites" },
  { id: 10, date: "2026-10-25", icon: "fa-sliders-h", title: () => t("Profil matériel"),
    text: () => t("Pimmich s'adapte à votre Raspberry Pi (2, 3, 4 ou 5) et propose des réglages conseillés."), route: "/maintenance" },
  { id: 9, date: "2026-10-25", icon: "fa-play-circle", title: () => t("Photos animées et courtes vidéos"),
    text: () => t("Les photos animées des téléphones s'animent comme des GIF ; les courtes vidéos tournent en boucle dans les dispositions."), route: "/preparation" },
  { id: 8, date: "2026-10-25", icon: "fa-compress-arrows-alt", title: () => t("Gagner de la place"),
    text: () => t("Les très gros originaux déjà prêts peuvent être remplacés par une version réduite."), route: "/preparation" },
  { id: 7, date: "2026-10-25", icon: "fa-moon", title: () => t("Le travail lourd la nuit"),
    text: () => t("Les grosses vidéos sont préparées quand le cadre est éteint ; les échecs sont réessayés chaque nuit."), route: "/affichage" },
  { id: 6, date: "2026-10-24", icon: "fa-cogs", title: () => t("Préparation des médias"),
    text: () => t("Tous les médias, préparés ou non, avec un bouton pour rattraper ceux restés de côté ; détails de l'import en cours."), route: "/preparation" },
  { id: 5, date: "2026-10-24", icon: "fa-paint-brush", title: () => t("Zone de dessin en plein écran"),
    text: () => t("Feutre fluo, texte, autocollants, gomme, fonds, pression du stylet : la page invités a été améliorée.") },
  { id: 4, date: "2026-10-24", icon: "fa-link", title: () => t("Adresse du cadre"),
    text: () => t("cadre-photo.local, .home ou Tailscale : plus besoin de connaître l'adresse IP."), route: "/reseau" },
  { id: 3, date: "2026-10-24", icon: "fa-film", title: () => t("GIF animés"),
    text: () => t("Acceptés par tous les imports et animés à l'écran, en photo seule comme dans les dispositions.") },
];

const KEY = "pimmich-news-seen";

export function lastSeen(): number {
  try { return Number(localStorage.getItem(KEY) || 0); } catch { return 0; }
}

export function markSeen(): void {
  try { localStorage.setItem(KEY, String(Math.max(...NEWS.map((n) => n.id)))); } catch { /* stockage indisponible */ }
}

export const unseen = (): News[] => NEWS.filter((n) => n.id > lastSeen());
