// Informations fournies par le serveur dans la page (/app) : langue, compte, droits.
export const boot: PimmichBoot = window.PIMMICH || { lang: "fr", user: "", admin: false, classic: "/configure" };

/** Interface classique : une rubrique précise, ou l'interface entière (choix retenu dans ce navigateur). */
export function classicUrl(tab?: string): string {
  return tab ? `${boot.classic}#${tab}` : `${boot.classic}?ui=classic`;
}
