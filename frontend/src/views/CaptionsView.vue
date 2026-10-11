<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import CaptionEditor from "../components/CaptionEditor.vue";
import { get } from "../api";
import { t } from "../i18n";

interface CaptionData { styles: Record<string, unknown>; samples: Record<string, string> }

const scopes = computed(() => [
  { key: "photo", icon: "fa-image", title: t("Photos et vidéos"), hint: t("Légende saisie sous chaque photo ou vidéo (aussi sur les cartes postales).") },
  { key: "polaroid", icon: "fa-camera-retro", title: t("Polaroïds"), hint: t("Texte écrit dans la marge blanche des polaroïds.") },
  { key: "metadata", icon: "fa-info-circle", title: t("Infos des photos"), hint: t("Date et lieu affichés par le diaporama.") },
]);
const previews = ref<Record<string, string>>({});
const editing = ref<string | null>(null);

async function loadPreviews() {
  const data = await get<CaptionData>("/api/captions");
  for (const scope of Object.keys(data.styles)) {
    const response = await fetch("/api/captions/preview", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
      body: JSON.stringify({ scope, style: data.styles[scope], text: data.samples[scope] }),
    });
    if (previews.value[scope]) URL.revokeObjectURL(previews.value[scope]);
    previews.value = { ...previews.value, [scope]: URL.createObjectURL(await response.blob()) };
  }
}

onMounted(loadPreviews);
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fas fa-closed-captioning"></i>{{ t("Style des légendes") }}</h2></div>
    <p class="small muted">{{ t("Choisissez l'apparence de chaque type de légende : police, taille, couleurs, fond, contour, ombre, position et inclinaison. Une photo ou une vidéo peut aussi avoir son propre style (depuis la bibliothèque).") }}</p>
    <div class="scopes">
      <article v-for="s in scopes" :key="s.key" class="scope">
        <img v-if="previews[s.key]" :src="previews[s.key]" alt="">
        <div v-else class="skeleton ph"></div>
        <div class="body">
          <strong><i class="fas" :class="s.icon"></i> {{ s.title }}</strong>
          <small class="muted">{{ s.hint }}</small>
          <button class="btn" type="button" @click="editing = s.key"><i class="fas fa-palette"></i>{{ t("Personnaliser") }}</button>
        </div>
      </article>
    </div>
    <p class="small muted note">{{ t("Les légendes déjà posées sur les photos sont redessinées automatiquement avec le nouveau style. Les vidéos affichent leur légende en sous-titre pendant la lecture.") }}</p>
  </section>
  <CaptionEditor v-if="editing" :scope="editing" @close="editing = null" @saved="loadPreviews" />
</template>

<style scoped>
.scopes { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-top: .8rem; }
.scope { border: 1px solid var(--border); border-radius: 14px; overflow: hidden; }
.scope img, .ph { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; }
.body { padding: .7rem .8rem .9rem; display: grid; gap: .4rem; }
.body i { color: var(--accent); }
.note { margin-top: 1rem; }
</style>
