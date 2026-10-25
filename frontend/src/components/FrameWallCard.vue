<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

// Mur de cadres : plusieurs cadres côte à côte affichent ensemble une même grande photo
interface Wall { enabled: boolean; order: string[]; gap: number; seconds: number }
const wall = ref<Wall | null>(null);
const frames = ref<{ id: string; name: string }[]>([]);

const nameOf = (id: string) => id === "self" ? t("Ce cadre") : frames.value.find((f) => f.id === id)?.name || id;
const unused = computed(() => ["self", ...frames.value.map((f) => f.id)].filter((id) => !wall.value?.order.includes(id)));

async function load() {
  try {
    const data = await get<{ wall: Wall; frames: { id: string; name: string }[] }>("/api/frames/wall");
    wall.value = data.wall; frames.value = data.frames;
  } catch { wall.value = null; }
}
async function save(change: Partial<Wall>) {
  const r = await run(() => post<{ success: boolean; message?: string; wall: Wall }>("/api/frames/wall", change, "PUT"));
  if (r?.wall) wall.value = r.wall;
}
function move(index: number, delta: number) {
  if (!wall.value) return;
  const order = [...wall.value.order];
  const [item] = order.splice(index, 1);
  order.splice(Math.max(0, Math.min(order.length, index + delta)), 0, item);
  save({ order });
}
const remove = (index: number) => wall.value && save({ order: wall.value.order.filter((_id, i) => i !== index) });
const add = (id: string) => wall.value && save({ order: [...wall.value.order, id] });

onMounted(load);
</script>

<template>
  <section v-if="wall && frames.length" class="card wall">
    <div class="card-head"><h2><i class="fas fa-border-all"></i>{{ t("Mur de cadres") }}</h2></div>
    <p class="small muted">{{ t("Posez plusieurs cadres côte à côte : ils affichent ensemble une même grande photo, découpée entre les écrans et changée en même temps sur tous. Idéal pour une fête.") }}</p>
    <ol class="order">
      <li v-for="(id, i) in wall.order" :key="id">
        <span class="spacer">{{ nameOf(id) }}</span>
        <button class="btn icon" type="button" :disabled="i === 0" :title="t('Vers la gauche')" @click="move(i, -1)"><i class="fas fa-arrow-left"></i></button>
        <button class="btn icon" type="button" :disabled="i === wall.order.length - 1" :title="t('Vers la droite')" @click="move(i, 1)"><i class="fas fa-arrow-right"></i></button>
        <button class="btn icon danger" type="button" :title="t('Retirer')" @click="remove(i)"><i class="fas fa-times"></i></button>
      </li>
    </ol>
    <div v-if="unused.length" class="row">
      <span class="small muted">{{ t("Ajouter à droite :") }}</span>
      <button v-for="id in unused" :key="id" class="btn small" type="button" @click="add(id)"><i class="fas fa-plus"></i> {{ nameOf(id) }}</button>
    </div>
    <div class="row">
      <label class="small">{{ t("Espace entre les écrans (% de la largeur)") }}
        <input type="number" min="0" max="30" :value="wall.gap" class="num" @change="save({ gap: Number(($event.target as HTMLInputElement).value) })"></label>
      <label class="small">{{ t("Chaque photo (secondes)") }}
        <input type="number" min="5" max="300" :value="wall.seconds" class="num" @change="save({ seconds: Number(($event.target as HTMLInputElement).value) })"></label>
    </div>
    <button class="btn" :class="wall.enabled ? 'danger' : 'primary'" type="button" :disabled="!wall.enabled && wall.order.length < 2" @click="save({ enabled: !wall.enabled })">
      <i class="fas" :class="wall.enabled ? 'fa-stop' : 'fa-play'"></i> {{ wall.enabled ? t("Arrêter le mur") : t("Lancer le mur") }}</button>
    <p v-if="wall.order.length < 2" class="small muted">{{ t("Il faut au moins deux écrans.") }}</p>
  </section>
</template>

<style scoped>
.wall { margin-top: 1rem; display: grid; gap: .6rem; justify-items: start; }
.order { margin: 0; padding-left: 1.4rem; width: 100%; display: grid; gap: .3rem; }
.order li { display: flex; gap: .3rem; align-items: center; }
.spacer { flex: 1; }
.row { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; }
.num { width: 4.5rem; margin-left: .3rem; }
</style>
