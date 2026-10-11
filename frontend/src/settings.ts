// Réglages (/api/settings) : chargés une fois, enregistrés automatiquement à chaque modification (regroupées).
import { reactive, ref } from "vue";
import { get, post } from "./api";
import { notify } from "./toast";

export type Value = string | number | boolean | null;

export const values = reactive<Record<string, Value>>({});
export const loaded = ref(false);
export const saving = ref(false);
const pending: Record<string, Value> = {};
let timer: number | undefined;

export async function loadSettings(): Promise<void> {
  const d = await get<{ values: Record<string, Value> }>("/api/settings");
  Object.assign(values, d.values);
  loaded.value = true;
}

export function setValue(key: string, value: Value): void {
  values[key] = value;
  pending[key] = value;
  window.clearTimeout(timer);
  timer = window.setTimeout(flush, 600);
}

async function flush(): Promise<void> {
  const changes = { ...pending };
  for (const key of Object.keys(changes)) delete pending[key];
  if (!Object.keys(changes).length) return;
  saving.value = true;
  try {
    const d = await post<{ message: string; values: Record<string, Value> }>("/api/settings", changes);
    Object.assign(values, d.values);
    notify(d.message);
  } catch (e) {
    notify((e as Error).message, true);
    await loadSettings();  // on revient aux valeurs enregistrées
  } finally {
    saving.value = false;
  }
}

export interface Field {
  key: string;
  label: () => string;
  type: "toggle" | "number" | "range" | "select" | "time" | "timeOrSunset";
  options?: () => { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  help?: () => string;
  showIf?: (v: Record<string, Value>) => boolean;
}

export interface Section { title: () => string; icon: string; intro?: () => string; fields: Field[] }
