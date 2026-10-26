<script setup lang="ts">
import { ref, watch } from "vue";
import { get, post } from "../api";
import { currentLang, t } from "../i18n";
import { run } from "../toast";

// Commentaires laissés par les invités sur cette photo (affichés en bandeau sur le cadre)
const props = defineProps<{ path: string }>();
interface Comment { text: string; name: string; at: number }
const comments = ref<Comment[]>([]);
const photo = () => `prepared/${props.path}`;

async function load() {
  try { comments.value = (await get<{ comments: Comment[] }>(`/api/photo_comments?photo=${encodeURIComponent(photo())}`)).comments; } catch { comments.value = []; }
}
async function remove(c: Comment) {
  if (!window.confirm(t("Supprimer ce commentaire ?"))) return;
  if (await run(() => post("/api/photo_comments", { photo: photo(), at: c.at }, "DELETE"))) load();
}
watch(() => props.path, load, { immediate: true });
</script>

<template>
  <ul v-if="comments.length" class="comments small">
    <li v-for="c in comments" :key="c.at">
      <span class="spacer">💬 « {{ c.text }} »<em v-if="c.name"> — {{ c.name }}</em>
        <span class="dim"> · {{ new Date(c.at * 1000).toLocaleDateString(currentLang()) }}</span></span>
      <button class="btn icon" type="button" :title="t('Supprimer ce commentaire')" @click="remove(c)"><i class="fas fa-times"></i></button>
    </li>
  </ul>
</template>

<style scoped>
.comments { list-style: none; margin: .3rem 0; padding: 0; display: grid; gap: .2rem; }
.comments li { display: flex; gap: .4rem; align-items: center; }
.spacer { flex: 1; }
.dim { opacity: .6; }
</style>
