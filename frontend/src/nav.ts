// Plan de l'interface : mêmes rubriques que l'interface classique. Une page déjà refaite a une `route` ;
// les autres ouvrent la rubrique correspondante de l'interface classique (en attendant d'être refaites).
import { t } from "./i18n";

export interface NavItem {
  label: () => string;
  icon: string;
  tab: string;
  route?: string;
  admin?: boolean;
}

export interface NavGroup {
  key: string;
  label: () => string;
  icon: string;
  items: NavItem[];
}

export const groups: NavGroup[] = [
  { key: "accueil", label: () => t("Accueil"), icon: "fa-home", items: [
    { label: () => t("Accueil"), icon: "fa-home", tab: "tab-accueil", route: "/" },
  ] },
  { key: "photos", label: () => t("Photos"), icon: "fa-images", items: [
    { label: () => t("Importer"), icon: "fa-file-import", tab: "tab-actions" },
    { label: () => t("Sources"), icon: "fa-folder-open", tab: "tab-sources" },
    { label: () => t("Bibliothèque"), icon: "fa-th", tab: "tab-apercu", route: "/bibliotheque" },
    { label: () => t("À suivre"), icon: "fa-stream", tab: "tab-queue", route: "/a-suivre" },
    { label: () => t("Playlists"), icon: "fa-list-ul", tab: "tab-playlists" },
    { label: () => t("Favoris"), icon: "fa-star", tab: "tab-favoris", route: "/favoris" },
    { label: () => t("Carte"), icon: "fa-globe-europe", tab: "tab-carte", route: "/carte" },
    { label: () => t("Messages"), icon: "fa-comment-alt", tab: "tab-messages" },
  ] },
  { key: "ecran", label: () => t("Écran"), icon: "fa-desktop", items: [
    { label: () => t("Dispositions"), icon: "fa-th-large", tab: "tab-dispositions" },
    { label: () => t("Affichage"), icon: "fa-desktop", tab: "tab-affichage" },
    { label: () => t("Horloge & météo"), icon: "fa-clock", tab: "tab-heure" },
    { label: () => t("Infos des photos"), icon: "fa-info-circle", tab: "tab-metadata" },
    { label: () => t("Légendes"), icon: "fa-closed-captioning", tab: "tab-legendes" },
    { label: () => t("Son"), icon: "fa-music", tab: "tab-son" },
  ] },
  { key: "partage", label: () => t("Partage"), icon: "fa-user-friends", items: [
    { label: () => t("Invités"), icon: "fa-qrcode", tab: "tab-invites" },
    { label: () => t("À valider"), icon: "fa-check-circle", tab: "tab-validation", route: "/a-valider" },
    { label: () => t("Telegram"), icon: "fa-paper-plane", tab: "tab-telegram" },
  ] },
  { key: "systeme", label: () => t("Système"), icon: "fa-cog", items: [
    { label: () => t("Comptes"), icon: "fa-users", tab: "tab-comptes" },
    { label: () => t("Notifications"), icon: "fa-bell", tab: "tab-notifications", admin: true },
    { label: () => t("Maintenance"), icon: "fa-tools", tab: "tab-maintenance", admin: true },
    { label: () => t("Réseau"), icon: "fa-wifi", tab: "tab-network", admin: true },
    { label: () => t("Commande vocale"), icon: "fa-microphone-alt", tab: "tab-vocal" },
    { label: () => t("Statistiques"), icon: "fa-chart-bar", tab: "tab-stats", admin: true, route: "/statistiques" },
    { label: () => t("Journaux"), icon: "fa-file-alt", tab: "tab-logs", admin: true },
  ] },
];

/** Rubrique de l'interface classique → page refaite (pour les liens « à corriger » de l'état du cadre). */
export function routeForTab(tab: string): string | undefined {
  for (const group of groups) {
    const item = group.items.find((i) => i.tab === tab);
    if (item) return item.route;
  }
  return undefined;
}
