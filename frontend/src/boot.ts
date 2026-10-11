// Informations fournies par le serveur dans la page (/app) : langue, compte, droits.
export const boot: PimmichBoot = window.PIMMICH || { lang: "fr", user: "", admin: false, classic: "/configure" };

export function classicUrl(tab?: string): string {
  return tab ? `${boot.classic}#${tab}` : boot.classic;
}
