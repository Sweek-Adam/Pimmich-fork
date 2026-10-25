<script setup lang="ts">
import { onMounted } from "vue";
import { currentLang, t } from "../i18n";
import { NEWS, lastSeen, markSeen } from "../news";

const seenBefore = lastSeen();
const dateLabel = (d: string) => new Date(d).toLocaleDateString(currentLang(), { day: "numeric", month: "long", year: "numeric" });
onMounted(markSeen);
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fas fa-gift"></i>{{ t("Nouveautés") }}</h2></div>
    <p class="small muted">{{ t("Les dernières fonctions du cadre, avec un raccourci vers chacune. Les questions fréquentes sont dans la FAQ du dépôt GitHub.") }}</p>
    <ul class="news">
      <li v-for="n in NEWS" :key="n.id" :class="{ fresh: n.id > seenBefore }">
        <i class="fas" :class="n.icon"></i>
        <div class="body">
          <div class="head"><strong>{{ n.title() }}</strong><span v-if="n.id > seenBefore" class="pill ok">{{ t("Nouveau") }}</span>
            <span class="small muted">{{ dateLabel(n.date) }}</span></div>
          <p class="small">{{ n.text() }}</p>
        </div>
        <router-link v-if="n.route" :to="n.route" class="btn small">{{ t("Voir") }}</router-link>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.news { list-style: none; margin: .5rem 0 0; padding: 0; display: grid; gap: .6rem; }
.news li { display: flex; gap: .8rem; align-items: center; padding: .7rem .8rem; border-radius: 12px; background: var(--surface-2); }
.news li.fresh { outline: 2px solid var(--accent-soft); }
.news li > i { font-size: 1.3rem; color: var(--accent); width: 1.6rem; text-align: center; }
.body { flex: 1; min-width: 0; }
.head { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.btn.small { padding: .3rem .7rem; font-size: .82rem; }
</style>
