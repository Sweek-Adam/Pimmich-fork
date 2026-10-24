<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface FrameName { name: string; where: "local" | "box" | "tailscale" }
interface WifiStatus { is_connected: boolean; ssid: string; ip_address: string; names?: FrameName[] }
interface Iface { state: string; ip_address?: string }
interface Network { ssid: string; signal: number; security: string }
interface Saved { name: string; uuid: string; priority: number; active: boolean; autoconnect: boolean }
interface Hotspot { enabled: boolean; active: boolean; ssid: string; address: string; password: string | null }

const status = ref<WifiStatus | null>(null);
const eth = ref<Iface | null>(null);
const form = reactive({ ssid: "", password: "", hidden: false });
const country = ref("FR");
const saved = ref<Saved[] | null>(null);
const hotspot = ref<Hotspot | null>(null);
const networks = ref<Network[] | null>(null);
const scanning = ref(false);
const applying = ref(false);

const countries = computed(() => [
  ["FR", t("France")], ["US", t("États-Unis")], ["GB", t("Royaume-Uni")], ["DE", t("Allemagne")],
  ["ES", t("Espagne")], ["CA", t("Canada")], ["BE", t("Belgique")], ["CH", t("Suisse")],
].map(([value, label]) => ({ value, label })));

async function loadStatus() {
  const [w, e] = await Promise.allSettled([get<WifiStatus>("/api/wifi_status"), get<Iface>("/api/interface_status/eth0")]);
  if (w.status === "fulfilled") status.value = w.value;
  if (e.status === "fulfilled") eth.value = e.value;
}

async function loadSaved() {
  try {
    const d = await get<{ networks: Saved[]; country: string; hotspot: Hotspot }>("/api/wifi/networks");
    saved.value = d.networks;
    country.value = d.country || "FR";
    hotspot.value = d.hotspot;
  } catch {
    saved.value = null;  // pas administrateur
  }
}

async function addNetwork() {
  applying.value = true;
  const done = await run(() => post("/api/wifi/networks", { ssid: form.ssid.trim(), password: form.password, hidden: form.hidden }));
  applying.value = false;
  if (done) Object.assign(form, { ssid: "", password: "", hidden: false });
  loadSaved();
}

async function forget(n: Saved) {
  const warning = n.active ? t("C'est le réseau utilisé en ce moment : le cadre peut ne plus être joignable. ") : "";
  if (!window.confirm(warning + t("Oublier le réseau « {name} » ?", { name: n.name }))) return;
  await run(() => post(`/api/wifi/networks/${n.uuid}`, {}, "DELETE"));
  loadSaved();
}

async function connectTo(n: Saved) {
  if (!window.confirm(t("Se connecter à « {name} » ? La connexion au cadre peut être coupée une minute.", { name: n.name }))) return;
  applying.value = true;
  await run(() => post(`/api/wifi/networks/${n.uuid}/connect`));
  applying.value = false;
  loadSaved();
  window.setTimeout(loadStatus, 5000);
}

async function move(index: number, delta: number) {
  if (!saved.value) return;
  const list = [...saved.value];
  const [item] = list.splice(index, 1);
  list.splice(index + delta, 0, item);
  saved.value = list;
  await run(() => post("/api/wifi/networks/order", { uuids: list.map((n) => n.uuid) }));
  loadSaved();
}

async function saveCountry() {
  await run(() => post("/api/wifi/country", { country: country.value }));
}

async function toggleHotspot(enabled: boolean) {
  await run(() => post("/api/settings", { wifi_hotspot_fallback: enabled }));
  loadSaved();
}

async function scan() {
  scanning.value = true;
  try {
    networks.value = (await get<{ networks: Network[] }>("/api/scan_wifi")).networks;
  } catch (e) {
    notify((e as Error).message, true);
  }
  scanning.value = false;
}

async function toggleEth() {
  if (!eth.value) return;
  const state = eth.value.state === "UP" ? "down" : "up";
  if (state === "down" && !window.confirm(t("Couper le réseau filaire ? Si le cadre n'a pas de Wi-Fi, il ne sera plus joignable."))) return;
  await run(() => post("/api/set_interface_state", { interface: "eth0", state }));
  window.setTimeout(loadStatus, 3000);
}

const whereLabel = (where: FrameName["where"]) => ({
  local: t("sur le même réseau (téléphone, ordinateur)"),
  box: t("enregistré par la box internet"),
  tailscale: t("depuis n'importe où, avec Tailscale"),
}[where]);

const bars = (signal: number) => (signal > 75 ? 4 : signal > 50 ? 3 : signal > 25 ? 2 : 1);

onMounted(async () => {
  loadStatus();
  loadSaved();
});
</script>

<template>
  <div class="grid grid-2 top">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-wifi"></i>{{ t("État de la connexion Wi-Fi") }}</h2>
        <button class="btn icon" type="button" :title="t('Actualiser')" @click="loadStatus"><i class="fas fa-sync-alt"></i></button></div>
      <dl v-if="status" class="facts">
        <dt>{{ t("État:") }}</dt><dd><span class="pill" :class="status.is_connected ? 'ok' : 'off'"><span class="dot"></span>{{ status.is_connected ? t("Connecté") : t("Non connecté") }}</span></dd>
        <dt>{{ t("Réseau (SSID):") }}</dt><dd>{{ status.ssid }}</dd>
        <dt>{{ t("Adresse IP:") }}</dt><dd>{{ status.ip_address }}</dd>
      </dl>
    </section>
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-network-wired"></i>{{ t("Interface Filaire (eth0)") }}</h2></div>
      <dl v-if="eth" class="facts">
        <dt>{{ t("État:") }}</dt><dd>{{ eth.state }}</dd>
        <dt>{{ t("Adresse IP:") }}</dt><dd>{{ eth.ip_address || "—" }}</dd>
      </dl>
      <button v-if="eth && eth.state !== 'NOT_FOUND'" class="btn" type="button" @click="toggleEth">
        {{ eth.state === "UP" ? t("Désactiver") : t("Activer") }}</button>
    </section>
  </div>

  <section v-if="status && status.names && status.names.length" class="card two">
    <div class="card-head"><h2><i class="fas fa-link"></i>{{ t("Adresse du cadre") }}</h2></div>
    <p class="small muted">{{ t("Tapez l'une de ces adresses dans le navigateur : elles restent valables même si l'adresse IP du cadre change.") }}</p>
    <ul class="names">
      <li v-for="n in status.names" :key="n.name"><a :href="`https://${n.name}`"><code>{{ n.name }}</code></a>
        <span class="small muted">{{ whereLabel(n.where) }}</span></li>
    </ul>
  </section>

  <div v-if="saved" class="grid grid-2 two">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-list-ol"></i>{{ t("Réseaux mémorisés") }}</h2></div>
      <p class="small muted">{{ t("Le cadre se connecte tout seul au premier réseau de la liste qui est à portée. Changez l'ordre avec les flèches.") }}</p>
      <ul class="saved">
        <li v-for="(n, i) in saved" :key="n.uuid">
          <span class="order">
            <button class="btn icon tiny" type="button" :disabled="i === 0" :title="t('Monter')" @click="move(i, -1)"><i class="fas fa-chevron-up"></i></button>
            <button class="btn icon tiny" type="button" :disabled="i === saved.length - 1" :title="t('Descendre')" @click="move(i, 1)"><i class="fas fa-chevron-down"></i></button>
          </span>
          <span class="spacer"><strong>{{ n.name }}</strong> <span v-if="n.active" class="pill ok small"><span class="dot"></span>{{ t("connecté") }}</span></span>
          <button v-if="!n.active" class="btn small" type="button" :disabled="applying" @click="connectTo(n)">{{ t("Se connecter") }}</button>
          <button class="btn small danger" type="button" @click="forget(n)">{{ t("Oublier") }}</button>
        </li>
        <li v-if="!saved.length" class="muted">{{ t("Aucun réseau mémorisé.") }}</li>
      </ul>
    </section>
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-plus"></i>{{ t("Ajouter un réseau") }}</h2></div>
      <p class="small muted">{{ t("Même s'il n'est pas à portée : pratique pour préparer le cadre avant de l'emporter ailleurs.") }}</p>
      <form class="fields" @submit.prevent="addNetwork">
        <label>{{ t("SSID (Nom du réseau)") }}<input v-model="form.ssid" type="text" maxlength="32" required></label>
        <label>{{ t("Mot de passe") }}<input v-model="form.password" type="password" autocomplete="new-password" maxlength="63"></label>
        <p class="small muted">{{ t("Laissez vide si le réseau est ouvert.") }}</p>
        <label class="check"><input v-model="form.hidden" type="checkbox">{{ t("Réseau masqué (son nom n'apparaît pas dans la liste)") }}</label>
        <div><button class="btn primary" type="submit" :disabled="applying || !form.ssid.trim()"><i class="fas fa-save"></i>{{ t("Mémoriser ce réseau") }}</button></div>
      </form>
      <div class="row country">
        <label>{{ t("Pays") }}<select v-model="country"><option v-for="c in countries" :key="c.value" :value="c.value">{{ c.label }}</option></select></label>
        <button class="btn small" type="button" @click="saveCountry">{{ t("Enregistrer") }}</button>
      </div>
    </section>
  </div>

  <section v-if="hotspot" class="card">
    <div class="card-head"><h2><i class="fas fa-satellite-dish"></i>{{ t("Point d'accès de secours") }}</h2>
      <span v-if="hotspot.active" class="pill ok"><span class="dot"></span>{{ t("ouvert en ce moment") }}</span></div>
    <p class="small muted">{{ t("Si aucun réseau connu n'est trouvé pendant 2 minutes, le cadre crée son propre Wi-Fi. Son nom, son mot de passe et un QR code s'affichent sur l'écran : connectez-y un téléphone, puis ouvrez l'adresse indiquée pour choisir un réseau. Toutes les 5 minutes, il réessaie les réseaux connus.") }}</p>
    <label class="check"><input type="checkbox" class="switch" :checked="hotspot.enabled" @change="toggleHotspot(($event.target as HTMLInputElement).checked)">{{ t("Activer le point d'accès de secours") }}</label>
    <dl v-if="hotspot.enabled" class="facts">
      <dt>{{ t("Nom du Wi-Fi") }}</dt><dd>{{ hotspot.ssid }}</dd>
      <dt>{{ t("Mot de passe") }}</dt><dd><code>{{ hotspot.password || t("créé à la première ouverture") }}</code></dd>
      <dt>{{ t("Adresse du cadre") }}</dt><dd>http://{{ hotspot.address }}</dd>
    </dl>
  </section>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-broadcast-tower"></i>{{ t("Réseaux Wi-Fi à proximité") }}</h2>
      <button class="btn" type="button" :disabled="scanning" @click="scan"><i class="fas" :class="scanning ? 'fa-spinner fa-spin' : 'fa-search'"></i>{{ t("Lancer le scan") }}</button></div>
    <ul v-if="networks" class="networks">
      <li v-for="n in networks" :key="n.ssid">
        <span class="signal" :class="'b' + bars(n.signal)"><i></i><i></i><i></i><i></i></span>
        <span class="spacer">{{ n.ssid }} <span class="small muted">· {{ n.security }}</span></span>
        <button class="btn small" type="button" @click="form.ssid = n.ssid; form.hidden = false">{{ t("Choisir") }}</button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.top { margin-bottom: 1rem; }
.two { margin-bottom: 1rem; }
.names { list-style: none; margin: .5rem 0 0; padding: 0; display: grid; gap: .4rem; }
.names li { display: flex; flex-wrap: wrap; align-items: baseline; gap: .6rem; }
.two .card + .card { margin-top: 0; }
.saved { list-style: none; padding: 0; margin: .4rem 0 0; }
.saved li { display: flex; align-items: center; gap: .5rem; padding: .45rem 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.order { display: inline-flex; flex-direction: column; gap: 2px; }
.btn.tiny { width: 1.7rem; height: 1.3rem; padding: 0; font-size: .7rem; }
.check { display: flex; align-items: center; gap: .5rem; font-weight: 600; }
.country { margin-top: 1rem; align-items: end; }
.country label { display: grid; gap: .25rem; font-weight: 600; font-size: .9rem; }
.country select { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; }
code { background: var(--surface-2); padding: .1rem .4rem; border-radius: 6px; }
.top .card + .card { margin-top: 0; }
.facts { display: grid; grid-template-columns: auto 1fr; gap: .4rem 1rem; margin: 0 0 .8rem; }
.facts dt { color: var(--muted); }
.facts dd { margin: 0; font-weight: 600; }
.fields { display: grid; gap: .7rem; max-width: 460px; }
.fields label { display: grid; gap: .25rem; font-weight: 600; font-size: .9rem; }
.fields input, .fields select { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; }
.networks { list-style: none; padding: 0; margin: 0; }
.networks li { display: flex; align-items: center; gap: .7rem; padding: .45rem 0; border-bottom: 1px solid var(--border); }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.signal { display: inline-flex; align-items: flex-end; gap: 2px; height: 16px; }
.signal i { width: 4px; background: var(--border); border-radius: 1px; }
.signal i:nth-child(1) { height: 25%; } .signal i:nth-child(2) { height: 50%; } .signal i:nth-child(3) { height: 75%; } .signal i:nth-child(4) { height: 100%; }
.b1 i:nth-child(-n+1), .b2 i:nth-child(-n+2), .b3 i:nth-child(-n+3), .b4 i:nth-child(-n+4) { background: var(--ok); }
</style>
