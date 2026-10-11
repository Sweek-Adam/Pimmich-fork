<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

interface Media { path: string; thumb: string; video: boolean; source: string; name: string }
interface Slot extends Partial<Media> { type: "photo" | "composition"; items?: Media[]; label?: string; image?: string; pending?: boolean }
interface Queue { running: boolean; current: Media | null; upcoming: Media[]; slots?: Slot[] }

const queue = ref<Queue | null>(null);
const slots = ref<Slot[]>([]);
const dragging = ref<number | null>(null);
let busyUntil = 0;
let timer: number | undefined;

const paths = (slot: Slot) => (slot.type === "composition" ? (slot.items ?? []).map((i) => i.path) : [slot.path!]);

async function refresh(force = false) {
  if (!force && Date.now() < busyUntil) return;
  try {
    const d = await get<Queue>("/api/slideshow/queue");
    queue.value = d;
    slots.value = d.slots ?? d.upcoming.map((m) => ({ ...m, type: "photo" as const }));
  } catch {
    queue.value = null;
  }
}

async function send(playNow = false) {
  busyUntil = Date.now() + 4000;
  await run(() => post("/api/slideshow/queue", { order: slots.value.flatMap(paths), play_now: playNow }));
  window.setTimeout(() => refresh(true), playNow ? 2500 : 4000);
}

function move(index: number, delta: number) {
  const target = index + delta;
  if (target < 0 || target >= slots.value.length) return;
  const list = [...slots.value];
  [list[index], list[target]] = [list[target], list[index]];
  slots.value = list;
  send();
}

function playNow(index: number) {
  const list = [...slots.value];
  list.unshift(...list.splice(index, 1));
  slots.value = list;
  send(true);
}

function drop(index: number) {
  if (dragging.value === null || dragging.value === index) return;
  const list = [...slots.value];
  const [moved] = list.splice(dragging.value, 1);
  list.splice(index, 0, moved);
  slots.value = list;
  dragging.value = null;
  send();
}

onMounted(() => {
  refresh(true);
  timer = window.setInterval(refresh, 8000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <div v-if="!queue" class="card"><div class="skeleton" style="height: 220px"></div></div>
  <section v-else-if="!queue.running" class="card empty">
    <i class="fas fa-moon"></i>
    <p>{{ t("Le diaporama est arrêté : la file d'attente apparaîtra quand il tournera.") }}</p>
  </section>
  <template v-else>
    <section v-if="queue.current" class="card current">
      <img :src="queue.current.thumb" alt="">
      <div>
        <p class="small muted">{{ t("À l'écran") }}</p>
        <strong>{{ queue.current.name }}</strong>
        <p class="small muted">{{ queue.current.source }}</p>
      </div>
    </section>
    <section class="card">
      <div class="card-head">
        <h2><i class="fas fa-stream"></i>{{ t("À suivre") }}</h2>
        <button class="btn icon" type="button" :title="t('Actualiser')" @click="refresh(true)"><i class="fas fa-sync-alt"></i></button>
      </div>
      <p class="small muted hint">{{ t("Glissez les photos pour changer l'ordre, ou utilisez les flèches ; ▶ l'affiche tout de suite.") }}</p>
      <ol class="slots">
        <li v-for="(slot, index) in slots" :key="paths(slot).join('|')" draggable="true" :class="{ group: slot.type === 'composition', dragging: dragging === index }"
            @dragstart="dragging = index" @dragend="dragging = null" @dragover.prevent @drop.prevent="drop(index)">
          <span class="num">{{ index + 1 }}</span>
          <div class="media">
            <img v-if="slot.type === 'composition' && slot.image" :src="slot.image" alt="" class="contain">
            <div v-else-if="slot.type === 'composition'" class="strip"><img v-for="item in slot.items" :key="item.path" :src="item.thumb" alt="" loading="lazy"></div>
            <img v-else :src="slot.thumb" alt="" loading="lazy">
          </div>
          <div class="text">
            <template v-if="slot.type === 'composition'">
              <strong><i class="fas fa-th-large"></i> {{ slot.pending ? t("Composition (commence ici, en préparation)") : slot.label }}</strong>
              <span class="small muted">{{ t("{n} photos", { n: slot.items?.length ?? 0 }) }}</span>
            </template>
            <template v-else>
              <strong><i v-if="slot.video" class="fas fa-video"></i> {{ slot.name }}</strong>
              <span class="small muted">{{ slot.source }}</span>
            </template>
          </div>
          <div class="actions">
            <button class="btn icon" type="button" :disabled="index === 0" :title="t('Monter')" @click="move(index, -1)"><i class="fas fa-arrow-up"></i></button>
            <button class="btn icon" type="button" :disabled="index === slots.length - 1" :title="t('Descendre')" @click="move(index, 1)"><i class="fas fa-arrow-down"></i></button>
            <button class="btn icon primary" type="button" :title="t('Afficher maintenant')" @click="playNow(index)"><i class="fas fa-play"></i></button>
          </div>
        </li>
      </ol>
    </section>
  </template>
</template>

<style scoped>
.empty { text-align: center; padding: 2.5rem 1rem; color: var(--muted); }
.empty i { font-size: 2rem; margin-bottom: .6rem; }
.current { display: flex; gap: 1rem; align-items: center; }
.current img { width: 160px; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 10px; }
.hint { margin-bottom: .7rem; }
.slots { list-style: none; margin: 0; padding: 0; display: grid; gap: .4rem; }
.slots li { display: flex; align-items: center; gap: .7rem; padding: .4rem; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); cursor: grab; }
.slots li.group { border-color: var(--accent); }
.slots li.dragging { opacity: .4; }
.num { width: 1.6rem; text-align: center; color: var(--muted); font-weight: 700; font-size: .85rem; }
.media { width: 110px; height: 62px; border-radius: 8px; overflow: hidden; background: #0d0f14; flex: none; }
.media img { width: 100%; height: 100%; object-fit: cover; }
.media img.contain { object-fit: contain; }
.strip { display: flex; height: 100%; }
.strip img { flex: 1; min-width: 0; }
.text { flex: 1; min-width: 0; display: grid; }
.text strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.text i { color: var(--accent); }
.actions { display: flex; gap: .3rem; }
.actions .btn.icon { width: 2.2rem; height: 2.2rem; }
@media (max-width: 760px) {
  .media { width: 80px; height: 50px; }
  .num { display: none; }
}
</style>
