// Traductions : les textes sont écrits en français (comme dans le reste de Pimmich) et traduits par les catalogues
// gettext du projet (translations/*.po), servis par /api/i18n. Paramètres : t("{n} photos", { n: 3 }).
import { reactive } from "vue";

const state = reactive({ lang: "fr", messages: {} as Record<string, string> });

export function t(msgid: string, params: Record<string, string | number> = {}): string {
  let text = state.messages[msgid] || msgid;
  for (const [key, value] of Object.entries(params)) {
    text = text.split(`{${key}}`).join(String(value));
  }
  return text;
}

export function currentLang(): string {
  return state.lang;
}

export async function loadMessages(lang: string): Promise<void> {
  state.lang = lang || "fr";
  document.documentElement.lang = state.lang;
  if (state.lang === "fr") return;
  try {
    const response = await fetch(`/api/i18n?lang=${encodeURIComponent(state.lang)}`, { credentials: "same-origin" });
    const data = await response.json();
    state.messages = data.messages || {};
  } catch {
    // textes en français si le catalogue ne répond pas
  }
}
