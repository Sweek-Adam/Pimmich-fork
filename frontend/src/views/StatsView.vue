<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { get } from "../api";
import { currentLang, t } from "../i18n";

interface Thumb { thumb: string; views?: number; reactions?: number }
interface Stats {
  sources: Record<string, { photos: number; videos: number }>;
  total_views: number;
  viewed: number;
  top: Thumb[];
  loved: Thumb[];
  per_day: { day: string; views: number }[];
}

const stats = ref<Stats | null>(null);
const error = ref("");
const COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4", "#a855f7", "#ec4899", "#84cc16", "#14b8a6", "#f97316"];

const sources = computed(() => {
  const entries = Object.entries(stats.value?.sources ?? {}).map(([key, s]) => ({
    name: key.startsWith("compte_") ? key.slice(7) : key, count: s.photos + s.videos, videos: s.videos,
  }));
  entries.sort((a, b) => b.count - a.count);
  return entries;
});
const total = computed(() => sources.value.reduce((n, s) => n + s.count, 0));
const maxDay = computed(() => Math.max(1, ...(stats.value?.per_day ?? []).map((d) => d.views)));
const dayLabel = (day: string) => new Date(day).toLocaleDateString(currentLang(), { day: "numeric", month: "short" });

onMounted(async () => {
  try {
    stats.value = await get<Stats>("/api/stats/photos");
  } catch (e) {
    error.value = (e as Error).message;
  }
});
</script>

<template>
  <p v-if="error" class="card">{{ error }}</p>
  <div v-else-if="!stats" class="card"><div class="skeleton" style="height: 260px"></div></div>
  <template v-else>
    <section class="card">
      <div class="totals">
        <div><strong>{{ total }}</strong><span>{{ t("photos et vidéos") }}</span></div>
        <div><strong>{{ stats.total_views }}</strong><span>{{ t("affichages comptés") }}</span></div>
        <div><strong>{{ stats.viewed }}</strong><span>{{ t("photos déjà vues") }}</span></div>
      </div>
    </section>

    <div class="grid grid-2" style="margin-top: 1rem">
      <section class="card">
        <div class="card-head"><h2><i class="fas fa-chart-pie"></i>{{ t("Répartition par source") }}</h2></div>
        <div class="stack">
          <span v-for="(s, i) in sources" :key="s.name" :style="{ width: (100 * s.count / Math.max(1, total)) + '%', background: COLORS[i % COLORS.length] }"></span>
        </div>
        <ul class="legend">
          <li v-for="(s, i) in sources" :key="s.name">
            <span class="swatch" :style="{ background: COLORS[i % COLORS.length] }"></span>
            <span class="spacer">{{ s.name }}</span><strong>{{ s.count }}</strong>
          </li>
        </ul>
      </section>

      <section class="card">
        <div class="card-head"><h2><i class="fas fa-chart-bar"></i>{{ t("Affichages par jour (14 jours)") }}</h2></div>
        <div class="bars">
          <div v-for="d in stats.per_day" :key="d.day" class="bar" :title="`${dayLabel(d.day)} : ${d.views}`">
            <span :style="{ height: (100 * d.views / maxDay) + '%' }"></span>
            <small>{{ dayLabel(d.day) }}</small>
          </div>
        </div>
      </section>
    </div>

    <section class="card" style="margin-top: 1rem">
      <div class="card-head"><h2><i class="fas fa-eye"></i>{{ t("Les plus vues") }}</h2></div>
      <p v-if="!stats.top.length" class="muted">{{ t("Pas encore de données.") }}</p>
      <div class="thumbs">
        <figure v-for="item in stats.top" :key="item.thumb" class="fig"><img :src="item.thumb" alt="" loading="lazy">
          <figcaption>{{ t("{n} fois", { n: item.views ?? 0 }) }}</figcaption></figure>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><h2><i class="fas fa-heart"></i>{{ t("Les plus aimées par les invités") }}</h2></div>
      <p v-if="!stats.loved.length" class="muted">{{ t("Pas encore de données.") }}</p>
      <div class="thumbs">
        <figure v-for="item in stats.loved" :key="item.thumb" class="fig"><img :src="item.thumb" alt="" loading="lazy">
          <figcaption>❤ {{ item.reactions }}</figcaption></figure>
      </div>
      <p class="small muted" style="margin-top: .8rem">{{ t("Les affichages sont comptés depuis la mise en place de cette fonction ; ils sont mis à jour toutes les 30 minutes.") }}</p>
    </section>
  </template>
</template>

<style scoped>
.totals { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; }
.totals div { background: var(--surface-2); border-radius: 12px; padding: .7rem; text-align: center; }
.totals strong { display: block; font-size: 1.5rem; }
.totals span { color: var(--muted); font-size: .85rem; }
.stack { display: flex; height: 14px; border-radius: 999px; overflow: hidden; background: var(--surface-2); }
.legend { list-style: none; padding: 0; margin: .8rem 0 0; display: grid; gap: .3rem; }
.legend li { display: flex; align-items: center; gap: .5rem; }
.swatch { width: .8rem; height: .8rem; border-radius: 4px; }
.bars { display: flex; align-items: flex-end; gap: 4px; height: 200px; }
.bar { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px; min-width: 0; }
.bar span { width: 100%; background: var(--accent); border-radius: 6px 6px 2px 2px; min-height: 2px; }
.bar small { font-size: .62rem; color: var(--muted); white-space: nowrap; overflow: hidden; max-width: 100%; }
.fig { margin: 0; position: relative; }
.fig figcaption { position: absolute; right: 6px; bottom: 6px; background: rgba(0, 0, 0, .65); color: #fff; font-size: .72rem; padding: 1px 7px; border-radius: 999px; }
</style>
