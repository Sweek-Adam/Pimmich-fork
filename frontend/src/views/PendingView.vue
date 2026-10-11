<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

interface Pending { photos: string[]; meta: Record<string, { name: string; device: boolean }> }
interface Trusted { id: string; label: string; since: string }

const pending = ref<Pending | null>(null);
const trusted = ref<Trusted[]>([]);
const zoom = ref<string | null>(null);
const working = ref<Set<string>>(new Set());

const url = (name: string) => `/static/pending_uploads/${encodeURIComponent(name)}`;
const isVideo = (name: string) => /\.(mp4|mov|avi|mkv)$/i.test(name);

async function load() {
  const [p, tr] = await Promise.allSettled([get<Pending>(`/api/get_pending_photos?_=${Date.now()}`), get<{ trusted: Trusted[] }>("/api/trusted_guests")]);
  if (p.status === "fulfilled") pending.value = p.value;
  if (tr.status === "fulfilled") trusted.value = tr.value.trusted;
  document.dispatchEvent(new Event("pimmich:pending"));
}

async function act(name: string, action: "approve" | "reject" | "trust") {
  working.value.add(name);
  const done = await run(() => post("/api/manage_pending_photo", { filename: name, action }));
  working.value.delete(name);
  if (done && pending.value) pending.value.photos = pending.value.photos.filter((p) => p !== name);
  if (action === "trust") load();
}

async function approveAll() {
  for (const name of [...(pending.value?.photos ?? [])]) await act(name, "approve");
}

async function untrust(item: Trusted) {
  await run(() => post(`/api/trusted_guests/${encodeURIComponent(item.id)}`, {}, "DELETE"));
  load();
}

onMounted(load);
</script>

<template>
  <section class="card">
    <div class="card-head">
      <h2><i class="fas fa-check-circle"></i>{{ t("Photos en attente de validation") }}</h2>
      <div class="row">
        <button v-if="pending && pending.photos.length > 1" class="btn" type="button" @click="approveAll"><i class="fas fa-check-double"></i>{{ t("Tout approuver") }}</button>
        <button class="btn icon" type="button" :title="t('Actualiser')" @click="load"><i class="fas fa-sync-alt"></i></button>
      </div>
    </div>
    <div v-if="!pending" class="skeleton" style="height: 160px"></div>
    <p v-else-if="!pending.photos.length" class="muted">{{ t("Aucune photo en attente de validation.") }}</p>
    <div v-else class="tiles">
      <figure v-for="name in pending.photos" :key="name" class="tile" :class="{ busy: working.has(name) }">
        <button type="button" class="media" @click="zoom = name">
          <video v-if="isVideo(name)" :src="url(name) + '#t=0.1'" preload="metadata" muted></video>
          <img v-else :src="url(name)" alt="" loading="lazy">
          <i v-if="isVideo(name)" class="fas fa-play play"></i>
        </button>
        <figcaption v-if="pending.meta[name]?.name">{{ pending.meta[name].name }}</figcaption>
        <div class="actions">
          <button class="btn ok" type="button" :title="t('Approuver')" @click="act(name, 'approve')"><i class="fas fa-check"></i></button>
          <button class="btn danger" type="button" :title="t('Rejeter')" @click="act(name, 'reject')"><i class="fas fa-times"></i></button>
          <button v-if="pending.meta[name]?.device" class="btn" type="button" :title="t('Approuver et toujours accepter cet appareil')" @click="act(name, 'trust')"><i class="fas fa-handshake"></i></button>
        </div>
      </figure>
    </div>
    <p class="small muted" style="margin-top: .9rem"><i class="fas fa-handshake"></i> {{ t("« Approuver et toujours accepter cet appareil » : les photos suivantes envoyées depuis ce téléphone s'afficheront sans attendre.") }}</p>
  </section>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-handshake"></i>{{ t("Appareils de confiance") }}</h2></div>
    <p v-if="!trusted.length" class="muted">{{ t("Aucun pour l'instant.") }}</p>
    <ul class="trusted">
      <li v-for="item in trusted" :key="item.id">
        <span class="spacer">{{ item.label }} <span class="muted small">· {{ item.since }}</span></span>
        <button class="btn" type="button" @click="untrust(item)">{{ t("Retirer la confiance") }}</button>
      </li>
    </ul>
  </section>

  <div v-if="zoom" class="viewer" @click="zoom = null">
    <video v-if="isVideo(zoom)" :src="url(zoom)" controls autoplay @click.stop></video>
    <img v-else :src="url(zoom)" alt="">
  </div>
</template>

<style scoped>
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: .8rem; }
.tile { margin: 0; display: grid; gap: .4rem; transition: opacity .2s; }
.tile.busy { opacity: .4; pointer-events: none; }
.media { position: relative; border: 0; padding: 0; background: var(--surface-2); border-radius: 12px; overflow: hidden; aspect-ratio: 1; cursor: zoom-in; }
.media img, .media video { width: 100%; height: 100%; object-fit: cover; }
.play { position: absolute; inset: 0; margin: auto; width: 2rem; height: 2rem; color: #fff; font-size: 1.6rem; text-shadow: 0 1px 6px rgba(0, 0, 0, .6); }
figcaption { font-size: .82rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.actions { display: flex; gap: .4rem; }
.actions .btn { flex: 1; padding: .4rem; }
.btn.ok { color: var(--ok); }
.trusted { list-style: none; margin: 0; padding: 0; }
.trusted li { display: flex; align-items: center; gap: .6rem; padding: .5rem 0; border-bottom: 1px solid var(--border); }
.trusted li:last-child { border-bottom: 0; }
.viewer { position: fixed; inset: 0; z-index: 60; background: rgba(0, 0, 0, .88); display: grid; place-items: center; padding: 1rem; cursor: zoom-out; }
.viewer img, .viewer video { max-width: 100%; max-height: 100%; border-radius: 8px; }
</style>
