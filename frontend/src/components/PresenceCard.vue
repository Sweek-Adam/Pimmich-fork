<script setup lang="ts">
import { onMounted, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

// Réveil à l'arrivée : téléphones de la famille reconnus sur le Wi-Fi
interface Device { mac: string; name: string; playlist: string | null; present?: boolean }
interface Seen { mac: string; ip: string; name: string | null }
const enabled = ref(false);
const devices = ref<Device[]>([]);
const detected = ref<Seen[]>([]);
const playlists = ref<{ id: string; name: string }[]>([]);
const loaded = ref(false);

async function load() {
  const [data, pls] = await Promise.all([
    get<{ enabled: boolean; devices: Device[]; detected: Seen[] }>("/api/presence"),
    get<{ id: string; name: string }[]>("/api/playlists").catch(() => []),
  ]);
  enabled.value = data.enabled;
  devices.value = data.devices;
  detected.value = data.detected;
  playlists.value = Array.isArray(pls) ? pls : [];
  loaded.value = true;
}

async function save() {
  const list = devices.value.map((d) => ({ mac: d.mac, name: d.name, playlist: d.playlist || null }));
  await run(() => post("/api/presence", { enabled: enabled.value, devices: list }));
}

async function add(seen: Seen) {
  devices.value.push({ mac: seen.mac, name: (seen.name || "").replace(/^(iPhone|Galaxy|Pixel)[-_ ]?(de[-_ ])?/i, ""), playlist: null });
  await save();
  load().catch(() => {});
}

async function remove(index: number) {
  devices.value.splice(index, 1);
  await save();
  load().catch(() => {});
}

onMounted(() => load().catch((e) => notify((e as Error).message, true)));
</script>

<template>
  <section v-if="loaded" class="card presence">
    <div class="card-head"><h2><i class="fas fa-door-open"></i>{{ t("Réveil à l'arrivée d'un membre de la famille") }}</h2></div>
    <p class="small muted">{{ t("Quand le téléphone d'une personne de la maison se reconnecte au Wi-Fi après une absence, le cadre se réveille (30 minutes, même la nuit), affiche « Bienvenue à la maison » et peut lancer sa playlist.") }}</p>
    <label class="check"><input v-model="enabled" type="checkbox" class="switch" @change="save">{{ t("Activer") }}</label>
    <ul class="list">
      <li v-for="(d, i) in devices" :key="d.mac">
        <span class="dot" :class="{ on: d.present }" :title="d.present ? t('à la maison') : t('absent')"></span>
        <input v-model="d.name" type="text" maxlength="40" :placeholder="t('Prénom')" class="name" @change="save">
        <small class="muted mac">{{ d.mac }}</small>
        <select v-model="d.playlist" @change="save">
          <option :value="null">{{ t("Pas de playlist") }}</option>
          <option v-for="p in playlists" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button class="btn small danger" type="button" @click="remove(i)">{{ t("Retirer") }}</button>
      </li>
    </ul>
    <details>
      <summary>{{ t("Ajouter un téléphone vu sur le Wi-Fi") }}</summary>
      <p class="small muted">{{ t("Allumez le Wi-Fi du téléphone puis actualisez. Astuce : sur iPhone et Android, désactivez « adresse privée / MAC aléatoire » pour ce réseau, sinon l'adresse change.") }}</p>
      <ul class="list">
        <li v-for="n in detected" :key="n.mac"><span class="spacer">{{ n.name || n.ip }} <small class="muted">· {{ n.mac }}</small></span>
          <button class="btn small" type="button" @click="add(n)"><i class="fas fa-plus"></i>{{ t("Ajouter") }}</button></li>
        <li v-if="!detected.length" class="muted">{{ t("Aucun appareil détecté.") }}</li>
      </ul>
      <button class="btn small" type="button" @click="load"><i class="fas fa-sync-alt"></i>{{ t("Actualiser") }}</button>
    </details>
  </section>
</template>

<style scoped>
.presence { margin-top: 1rem; }
.check { display: flex; align-items: center; gap: .5rem; margin: .6rem 0; font-weight: 600; }
.list { list-style: none; padding: 0; margin: .4rem 0; }
.list li { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; padding: .45rem 0; border-bottom: 1px solid var(--border); }
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--muted); flex: none; }
.dot.on { background: var(--ok); }
.name { flex: 1 1 120px; }
.mac { font-family: ui-monospace, monospace; }
input[type="text"], select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .35rem .55rem; min-width: 0; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
summary { cursor: pointer; color: var(--accent); font-weight: 600; margin-top: .4rem; }
</style>
