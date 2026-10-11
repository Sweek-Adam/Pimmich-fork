<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

const logs = ref<{ key: string; name: string }[]>([]);
const current = ref("app");
const content = ref("");
const filter = ref("");
const errorsOnly = ref(false);
const follow = ref(true);
const box = ref<HTMLElement | null>(null);
let timer: number | undefined;

const ERROR = /❌|error|erreur|traceback|exception|warning|⚠️/i;
const lines = computed(() => {
  const words = filter.value.trim().toLowerCase();
  return content.value.split("\n").filter((line) => line.trim()
    && (!errorsOnly.value || ERROR.test(line)) && (!words || line.toLowerCase().includes(words)));
});

async function load() {
  try {
    content.value = (await get<{ content: string }>(`/api/logs?type=${encodeURIComponent(current.value)}`)).content;
    if (follow.value) {
      await nextTick();
      box.value?.scrollTo({ top: box.value.scrollHeight });
    }
  } catch (e) {
    notify((e as Error).message, true);
  }
}

async function clear() {
  if (!window.confirm(t("Effacer ce journal ?"))) return;
  await run(() => post("/api/clear_logs", { type: current.value }));
  load();
}

watch(current, load);
onMounted(async () => {
  try {
    logs.value = (await get<{ logs: { key: string; name: string }[] }>("/api/list_logs")).logs;
  } catch {
    logs.value = [];
  }
  load();
  timer = window.setInterval(() => { if (follow.value) load(); }, 5000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section class="card">
    <div class="row toolbar">
      <select v-model="current">
        <option v-for="log in logs" :key="log.key" :value="log.key">{{ log.name }}</option>
      </select>
      <input v-model="filter" type="search" class="spacer" :placeholder="t('Filtrer…')">
      <label class="check"><input v-model="errorsOnly" type="checkbox">{{ t("Erreurs seulement") }}</label>
      <label class="check"><input v-model="follow" type="checkbox">{{ t("Suivre en direct") }}</label>
      <button class="btn icon" type="button" :title="t('Actualiser')" @click="load"><i class="fas fa-sync-alt"></i></button>
      <button class="btn icon danger" type="button" :title="t('Effacer')" @click="clear"><i class="fas fa-trash-alt"></i></button>
    </div>
    <p class="small muted">{{ t("{n} lignes affichées (les 500 dernières du fichier)", { n: lines.length }) }}</p>
    <div ref="box" class="log">
      <div v-for="(line, i) in lines" :key="i" :class="{ err: ERROR.test(line) }">{{ line }}</div>
    </div>
  </section>
</template>

<style scoped>
.toolbar { margin-bottom: .6rem; }
.toolbar input[type="search"] { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; min-width: 160px; }
.check { display: flex; gap: .4rem; align-items: center; font-size: .9rem; }
.log { margin-top: .6rem; height: 65vh; overflow: auto; background: #0f1117; color: #d6d9e3; border-radius: 12px; padding: .8rem;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; word-break: break-word; }
.log .err { color: #ff9b8f; }
</style>
