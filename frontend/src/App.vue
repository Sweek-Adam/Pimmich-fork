<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import { boot, classicUrl } from "./boot";
import { groups, type NavGroup, type NavItem } from "./nav";
import { get } from "./api";
import { t } from "./i18n";
import { applyTheme, theme, type Theme } from "./theme";
import { toast } from "./toast";

const route = useRoute();
const status = ref<{ running: boolean; paused: boolean } | null>(null);
const sheet = ref<NavGroup | null>(null);
const pendingCount = ref(0);
interface ImportItem { source: string; label: string; phase: string; active: boolean; download: { percent: number }; prepare: { percent: number } }
const imports = ref<ImportItem[]>([]);
async function refreshImports() {
  try { imports.value = (await get<{ imports: ImportItem[] }>("/api/imports/progress")).imports; } catch { imports.value = []; }
}
let timer: number | undefined;

const visibleGroups = computed(() =>
  groups.map((g) => ({ ...g, items: g.items.filter((i) => !i.admin || boot.admin) })),
);

const current = computed<NavItem | undefined>(() => {
  for (const group of groups) {
    const item = group.items.find((i) => i.route === route.path);
    if (item) return item;
  }
  return undefined;
});

const currentGroup = computed(() => groups.find((g) => g.items.some((i) => i.route === route.path))?.key);

async function refreshStatus() {
  try {
    status.value = await get<{ running: boolean; paused: boolean }>("/api/slideshow/status");
  } catch {
    status.value = null;
  }
}

async function refreshPending() {
  try {
    pendingCount.value = (await get<{ photos: string[] }>(`/api/get_pending_photos?_=${Date.now()}`)).photos.length;
  } catch {
    pendingCount.value = 0;
  }
}

/** Pastille d'une rubrique (photos des invités à valider). */
function badge(item: NavItem): number {
  return item.tab === "tab-validation" ? pendingCount.value : 0;
}
const groupBadge = (group: NavGroup) => group.items.reduce((n, i) => n + badge(i), 0);

const themes: Theme[] = ["auto", "light", "dark"];
const themeIcon = computed(() => ({ auto: "fa-adjust", light: "fa-sun", dark: "fa-moon" })[theme.value]);
function cycleTheme() {
  applyTheme(themes[(themes.indexOf(theme.value) + 1) % themes.length]);
}

function openGroup(group: NavGroup) {
  const items = group.items.filter((i) => !i.admin || boot.admin);
  sheet.value = items.length === 1 && items[0].route ? null : { ...group, items };
}

onMounted(() => {
  refreshStatus();
  refreshPending();
  refreshImports();
  timer = window.setInterval(() => { refreshStatus(); refreshPending(); refreshImports(); }, 15000);
  document.addEventListener("pimmich:status", refreshStatus);
  document.addEventListener("pimmich:pending", refreshPending);
});
onUnmounted(() => {
  window.clearInterval(timer);
  document.removeEventListener("pimmich:status", refreshStatus);
  document.removeEventListener("pimmich:pending", refreshPending);
});
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <router-link to="/" class="brand"><img src="/static/pimmich_logo.png" alt=""><span>Pimmich</span></router-link>
      <nav>
        <section v-for="group in visibleGroups" :key="group.key">
          <h4>{{ group.label() }}</h4>
          <template v-for="item in group.items" :key="item.tab">
            <router-link v-if="item.route" :to="item.route" class="nav-item" :class="{ active: route.path === item.route }">
              <i class="fas fa-fw" :class="item.icon"></i>{{ item.label() }}<span v-if="badge(item)" class="badge">{{ badge(item) }}</span>
            </router-link>
            <a v-else :href="classicUrl(item.tab)" class="nav-item classic" :title="t('Ouvre l\'interface classique')">
              <i class="fas fa-fw" :class="item.icon"></i>{{ item.label() }}<i class="fas fa-external-link-alt ext"></i>
            </a>
          </template>
        </section>
      </nav>
      <a :href="classicUrl()" class="back-classic"><i class="fas fa-undo fa-fw"></i>{{ t("Interface classique") }}</a>
    </aside>

    <div class="main">
      <header class="topbar">
        <h1>{{ current ? current.label() : "Pimmich" }}</h1>
        <span class="beta">{{ t("Nouvelle interface (essai)") }}</span>
        <span class="spacer"></span>
        <span v-if="status" class="pill" :class="status.running ? (status.paused ? 'warn' : 'ok') : 'off'">
          <span class="dot"></span>{{ status.running ? (status.paused ? t("En pause") : t("En marche")) : t("Arrêté") }}
        </span>
        <button class="btn icon" type="button" :title="t('Thème')" @click="cycleTheme"><i class="fas" :class="themeIcon"></i></button>
      </header>
      <main class="content">
        <router-view :key="route.path" />
      </main>
    </div>

    <nav class="bottom-nav">
      <button v-for="group in visibleGroups" :key="group.key" type="button" :class="{ active: currentGroup === group.key }"
              @click="group.items.length === 1 && group.items[0].route ? $router.push(group.items[0].route) : openGroup(group)">
        <i class="fas" :class="group.icon"></i><span>{{ group.label() }}</span><b v-if="groupBadge(group)" class="dot-badge">{{ groupBadge(group) }}</b>
      </button>
    </nav>

    <div v-if="sheet" class="sheet-backdrop" @click.self="sheet = null">
      <div class="sheet">
        <h3>{{ sheet.label() }}</h3>
        <template v-for="item in sheet.items" :key="item.tab">
          <router-link v-if="item.route" :to="item.route" class="nav-item" @click="sheet = null">
            <i class="fas fa-fw" :class="item.icon"></i>{{ item.label() }}<span v-if="badge(item)" class="badge">{{ badge(item) }}</span>
          </router-link>
          <a v-else :href="classicUrl(item.tab)" class="nav-item classic">
            <i class="fas fa-fw" :class="item.icon"></i>{{ item.label() }}<i class="fas fa-external-link-alt ext"></i>
          </a>
        </template>
        <a :href="classicUrl()" class="nav-item"><i class="fas fa-undo fa-fw"></i>{{ t("Interface classique") }}</a>
      </div>
    </div>

    <div v-if="imports.length" class="imports">
      <div v-for="item in imports" :key="item.source" class="import-item">
        <i class="fas" :class="item.active ? 'fa-sync-alt fa-spin' : 'fa-check-circle'"></i>
        <span class="spacer">{{ item.label }} · {{ item.phase === "prepare" ? t("préparation") : t("téléchargement") }}</span>
        <strong>{{ item.phase === "prepare" ? item.prepare.percent : item.download.percent }}%</strong>
      </div>
    </div>
    <div v-if="toast.text" class="toast" :class="{ error: toast.error }" role="status">{{ toast.text }}</div>
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; }
.sidebar {
  position: fixed; inset: 0 auto 0 0; width: var(--sidebar); background: var(--surface); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 1rem .8rem; overflow-y: auto;
}
.brand { display: flex; align-items: center; gap: .6rem; font-weight: 800; font-size: 1.15rem; color: var(--text); padding: .2rem .5rem 1rem; }
.brand:hover { text-decoration: none; }
.brand img { width: 30px; height: 30px; }
nav section { margin-bottom: .9rem; }
nav h4 { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); padding: 0 .6rem .3rem; }
.nav-item {
  display: flex; align-items: center; gap: .6rem; padding: .42rem .6rem; border-radius: 10px; color: var(--text); font-weight: 500;
}
.nav-item:hover { background: var(--surface-2); text-decoration: none; }
.nav-item.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.nav-item i:first-child { color: var(--muted); }
.nav-item.active i:first-child { color: var(--accent); }
.nav-item.classic { color: var(--muted); }
.badge { margin-left: auto; background: var(--danger); color: #fff; font-size: .7rem; font-weight: 700; border-radius: 999px; padding: 0 .45rem; }
.ext { margin-left: auto; font-size: .65rem; opacity: .6; }
.back-classic { margin-top: auto; padding: .6rem; color: var(--muted); font-size: .9rem; display: flex; gap: .5rem; align-items: center; }

.main { margin-left: var(--sidebar); }
.topbar {
  position: sticky; top: 0; z-index: 10; display: flex; align-items: center; gap: .75rem;
  padding: .8rem 1.5rem; background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}
.beta { font-size: .72rem; color: var(--accent); background: var(--accent-soft); border-radius: 999px; padding: .1rem .55rem; font-weight: 600; }
.content { padding: 1.3rem 1.5rem 2.5rem; max-width: 1200px; }

.bottom-nav { display: none; }
.imports { position: fixed; right: 1rem; bottom: 1rem; z-index: 30; display: grid; gap: .4rem; width: min(320px, calc(100vw - 2rem)); }
.import-item { display: flex; align-items: center; gap: .6rem; background: var(--surface); border: 1px solid var(--border); box-shadow: var(--shadow); border-radius: 12px; padding: .55rem .8rem; font-size: .88rem; }
.import-item i { color: var(--accent); }
@media (max-width: 760px) { .imports { bottom: calc(4.6rem + env(safe-area-inset-bottom)); right: .5rem; } }
.sheet-backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); z-index: 40; display: flex; align-items: flex-end; }
.sheet {
  width: 100%; background: var(--surface); border-radius: 20px 20px 0 0; padding: 1rem 1rem calc(5rem + env(safe-area-inset-bottom));
  max-height: 80vh; overflow-y: auto;
}
.sheet h3 { padding: .2rem .6rem .6rem; }

@media (max-width: 760px) {
  .sidebar { display: none; }
  .main { margin-left: 0; }
  .topbar { padding: .7rem 1rem; }
  .topbar h1 { font-size: 1.15rem; }
  .beta { display: none; }
  .content { padding: 1rem 1rem calc(5.5rem + env(safe-area-inset-bottom)); }
  .bottom-nav {
    display: flex; position: fixed; inset: auto 0 0 0; z-index: 45; background: var(--surface); border-top: 1px solid var(--border);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .bottom-nav button {
    flex: 1; border: 0; background: none; color: var(--muted); font: inherit; font-size: .7rem; padding: .55rem 0 .5rem;
    display: flex; flex-direction: column; align-items: center; gap: .2rem; cursor: pointer;
  }
  .bottom-nav button i { font-size: 1.1rem; }
  .bottom-nav button.active { color: var(--accent); }
  .bottom-nav button { position: relative; }
  .dot-badge { position: absolute; top: .3rem; left: calc(50% + .4rem); background: var(--danger); color: #fff; font-size: .62rem; border-radius: 999px; padding: 0 .35rem; }
}
</style>
