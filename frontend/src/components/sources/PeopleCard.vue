<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../../api";
import { t } from "../../i18n";
import { notify, run } from "../../toast";

interface Person { id: string; name: string; count: number; on_frame: number; followed: boolean; playlist: boolean; thumb: string }
const data = ref<{ configured: boolean; people: Person[] } | null>(null);
async function load() { data.value = await get("/api/people"); }
async function act(url: string, body: Record<string, unknown> = {}) { await run(() => post(url, body)); load(); }
async function refresh() { notify(t("Mise à jour…")); await act("/api/people/refresh"); }
onMounted(() => load().catch(() => {}));
</script>

<template>
  <section class="card">
    <div class="card-head"><h2><i class="fas fa-user-friends"></i>{{ t("Personnes") }}</h2>
      <button class="btn small" type="button" @click="refresh"><i class="fas fa-sync-alt"></i>{{ t("Mettre à jour depuis Immich") }}</button></div>
    <p v-if="data && !data.configured" class="small muted">{{ t("Configurez Immich ci-dessus pour retrouver les personnes.") }}</p>
    <p v-else-if="data && !data.people.length" class="small muted">{{ t("Aucune personne nommée pour l'instant : nommez les visages dans Immich, puis mettez à jour.") }}</p>
    <div class="people">
      <article v-for="p in data?.people || []" :key="p.id" class="person">
        <img :src="p.thumb" alt="" loading="lazy">
        <div><strong>{{ p.name }}</strong><small class="muted">{{ t("{n} sur le cadre / {total} dans Immich", { n: p.on_frame, total: p.count }) }}</small>
          <div class="row">
            <button class="btn small primary" type="button" @click="act(`/api/people/${p.id}/play`)">{{ t("Afficher ses photos") }}</button>
            <button class="btn small" type="button" @click="act(`/api/people/${p.id}/follow`, { follow: !p.followed })">{{ p.followed ? t("Suivie ✓") : t("Suivre") }}</button>
            <button v-if="!p.playlist" class="btn small" type="button" @click="act(`/api/people/${p.id}/play`, { create_only: true })">{{ t("Créer sa playlist") }}</button>
          </div></div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.people { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: .7rem; }
.person { display: flex; gap: .7rem; align-items: center; border: 1px solid var(--border); border-radius: 12px; padding: .6rem; }
.person img { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; }
.person div { display: grid; gap: .3rem; }
.btn.small { padding: .25rem .7rem; font-size: .8rem; }
</style>
