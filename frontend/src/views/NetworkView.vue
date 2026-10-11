<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface WifiStatus { is_connected: boolean; ssid: string; ip_address: string }
interface Iface { state: string; ip_address?: string }
interface Network { ssid: string; signal: number; security: string }

const status = ref<WifiStatus | null>(null);
const eth = ref<Iface | null>(null);
const form = reactive({ ssid: "", password: "", country: "FR", hasPassword: false });
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

async function apply() {
  if (!window.confirm(t("Appliquer ces paramètres Wi-Fi ? La connexion au cadre peut être coupée une minute."))) return;
  applying.value = true;
  await run(() => post("/api/wifi", { ssid: form.ssid, country: form.country, ...(form.password ? { password: form.password } : {}) }));
  applying.value = false;
  form.password = "";
  window.setTimeout(loadStatus, 20000);
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

const bars = (signal: number) => (signal > 75 ? 4 : signal > 50 ? 3 : signal > 25 ? 2 : 1);

onMounted(async () => {
  loadStatus();
  try {
    const d = await get<{ ssid: string; country: string; has_password: boolean }>("/api/wifi");
    Object.assign(form, { ssid: d.ssid, country: d.country || "FR", hasPassword: d.has_password });
  } catch {
    // pas administrateur
  }
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

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-cog"></i>{{ t("Configuration Wi-Fi") }}</h2></div>
    <form class="fields" @submit.prevent="apply">
      <label>{{ t("Pays") }}<select v-model="form.country"><option v-for="c in countries" :key="c.value" :value="c.value">{{ c.label }}</option></select></label>
      <label>{{ t("SSID (Nom du réseau)") }}<input v-model="form.ssid" type="text" required></label>
      <label>{{ t("Mot de passe") }}<input v-model="form.password" type="password" autocomplete="new-password"
        :placeholder="form.hasPassword ? t('Enregistré (laisser vide pour garder)') : ''"></label>
      <p class="small muted">{{ t("Laissez vide si le réseau est ouvert.") }}</p>
      <div><button class="btn primary" type="submit" :disabled="applying || !form.ssid"><i class="fas fa-check"></i>{{ t("Appliquer les paramètres Wi-Fi") }}</button></div>
    </form>
  </section>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-broadcast-tower"></i>{{ t("Réseaux Wi-Fi à proximité") }}</h2>
      <button class="btn" type="button" :disabled="scanning" @click="scan"><i class="fas" :class="scanning ? 'fa-spinner fa-spin' : 'fa-search'"></i>{{ t("Lancer le scan") }}</button></div>
    <ul v-if="networks" class="networks">
      <li v-for="n in networks" :key="n.ssid">
        <span class="signal" :class="'b' + bars(n.signal)"><i></i><i></i><i></i><i></i></span>
        <span class="spacer">{{ n.ssid }} <span class="small muted">· {{ n.security }}</span></span>
        <button class="btn small" type="button" @click="form.ssid = n.ssid">{{ t("Choisir") }}</button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.top { margin-bottom: 1rem; }
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
