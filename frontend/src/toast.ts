// Message bref en bas de l'écran (résultat d'une action).
import { reactive } from "vue";

export const toast = reactive({ text: "", error: false });
let timer: number | undefined;

export function notify(text: string, error = false): void {
  toast.text = text;
  toast.error = error;
  window.clearTimeout(timer);
  timer = window.setTimeout(() => (toast.text = ""), error ? 6000 : 3500);
}

/** Lance une action et affiche son message (ou l'erreur). */
export async function run<T extends { message?: string }>(action: () => Promise<T>, fallback = ""): Promise<T | undefined> {
  try {
    const result = await action();
    if (result?.message || fallback) notify(result?.message || fallback);
    return result;
  } catch (e) {
    notify((e as Error).message, true);
    return undefined;
  }
}
