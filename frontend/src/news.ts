// Nouveautés du cadre (page « Nouveautés » et bandeau de l'accueil). Ajouter les plus récentes en tête.
import { t } from "./i18n";

export interface News { id: number; date: string; icon: string; title: () => string; text: () => string; route?: string }

export const NEWS: News[] = [
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
