<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

// Citation du jour : citations célèbres (dans la langue du cadre) et « mots de la famille »
interface Quote { text: string; author: string }
interface Quotes { enabled: boolean; mode: string; style: string; family: Quote[]; today: Quote | null; styles: string[] }
const data = ref<Quotes | null>(null);
const family = ref("");
const preview = ref("");

const styleLabels = (): Record<string, string> => ({
  carte: t("Carte postale"), nuit: t("Nuit"), pastel: t("Pastel"), ardoise: t("Ardoise"), minimal: t("Minimal"), lettre: t("Lettre"),
});

async function load() {
  data.value = await get<Quotes>("/api/quotes");
  family.value = data.value.family.map((q) => (q.author ? `${q.text} — ${q.author}` : q.text)).join("\n");
  preview.value = data.value.today ? `/api/quotes/preview?t=${Date.now()}` : "";
}

function parse(): Quote[] {
  return family.value.split("\n").map((l) => l.trim()).filter(Boolean).map((line) => {
    const dash = line.lastIndexOf(" — ") >= 0 ? line.lastIndexOf(" — ") : line.lastIndexOf(" - ");
    return dash > 0 ? { text: line.slice(0, dash).trim(), author: line.slice(dash + 3).trim() } : { text: line, author: "" };
  });
}

async function save() {
  if (!data.value) return;
  const done = await run(() => post("/api/quotes", { enabled: data.value!.enabled, mode: data.value!.mode, style: data.value!.style, family: parse() }));
  if (done) window.setTimeout(() => load().catch(() => {}), 1500);  // la citation du jour est redessinée en arrière-plan
}

onMounted(() => load().catch((e) => notify((e as Error).message, true)));
</script>

<template>
  <section class="card quote">
    <div class="card-head"><h2><i class="fas fa-quote-left"></i>{{ t("Citation du jour") }}</h2></div>
    <div v-if="!data" class="skeleton" style="height: 120px"></div>
    <template v-else>
      <p class="small muted">{{ t("Chaque jour, une citation ou un proverbe (dans la langue du cadre), ou un mot de la famille, apparaît dans le diaporama, environ une fois par tour.") }}</p>
      <label class="check"><input v-model="data.enabled" type="checkbox" class="switch" @change="save">{{ t("Afficher une citation du jour") }}</label>
      <div class="fields">
        <label>{{ t("Citations :") }}
          <select v-model="data.mode" @change="save">
            <option value="all">{{ t("Célèbres et mots de la famille") }}</option>
            <option value="builtin">{{ t("Citations et proverbes célèbres") }}</option>
            <option value="family">{{ t("Seulement les mots de la famille") }}</option>
          </select></label>
        <label>{{ t("Présentation :") }}
          <select v-model="data.style" @change="save">
            <option value="auto">{{ t("Une différente chaque jour") }}</option>
            <option v-for="s in data.styles" :key="s" :value="s">{{ styleLabels()[s] || s }}</option>
          </select></label>
      </div>
      <label class="field">{{ t("Les mots de la famille") }}
        <textarea v-model="family" rows="4" :placeholder="t('On n\'est pas aux pièces ! — Papi')"></textarea></label>
      <p class="small muted">{{ t("Les phrases cultes de la maison, une par ligne. Ajoutez l'auteur après un tiret : « On n'est pas aux pièces ! — Papi ».") }}</p>
      <button class="btn primary" type="button" @click="save"><i class="fas fa-check"></i>{{ t("Enregistrer") }}</button>
      <p class="small today"><strong>{{ t("Aujourd'hui :") }}</strong> {{ data.today ? `${data.today.text}${data.today.author ? " — " + data.today.author : ""}` : "—" }}</p>
      <img v-if="preview" :src="preview" alt="" class="preview">
    </template>
  </section>
</template>

<style scoped>
.quote { margin-top: 1rem; }
.check { display: flex; align-items: center; gap: .5rem; margin: .6rem 0; font-weight: 600; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: .6rem; margin-bottom: .6rem; }
.fields label, .field { display: grid; gap: .25rem; font-size: .9rem; font-weight: 600; }
select, textarea { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .6rem; min-width: 0; }
textarea { resize: vertical; }
.today { margin-top: .8rem; }
.preview { width: 100%; max-width: 480px; border-radius: 12px; margin-top: .4rem; box-shadow: var(--shadow); }
</style>
