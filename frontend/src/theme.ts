// Thème clair / sombre / automatique, partagé avec l'interface classique (même clé localStorage).
import { ref } from "vue";

export type Theme = "auto" | "light" | "dark";
const KEY = "pimmich-theme";

function read(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "auto";
  } catch {
    return "auto";
  }
}

export const theme = ref<Theme>(read());

export function applyTheme(value: Theme = theme.value): void {
  theme.value = value;
  const root = document.documentElement;
  if (value === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", value);
  try {
    localStorage.setItem(KEY, value);
  } catch {
    // navigation privée : le choix ne sera pas retenu
  }
}
