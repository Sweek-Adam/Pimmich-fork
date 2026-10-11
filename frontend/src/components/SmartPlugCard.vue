<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { values } from "../settings";
import { run } from "../toast";

// Test des adresses de la prise connectée et état de la prise (si une adresse de statut est renseignée)
const status = ref<{ status: string; message: string } | null>(null);
const busy = ref(false);

async function test(key: string) {
  busy.value = true;
  await run(() => post("/api/test_smart_plug", { url: values[key] }));
  busy.value = false;
  loadStatus();
}

async function loadStatus() {
  if (!values.smart_plug_enabled || !values.smart_plug_status_url) { status.value = null; return; }
  try { status.value = await get("/api/smart_plug/status"); } catch { status.value = null; }
}

const on = () => ["on", "true", "1"].includes(status.value?.status || "");
watch(() => [values.smart_plug_enabled, values.smart_plug_status_url], loadStatus);
onMounted(loadStatus);
</script>

<template>
  <section v-if="values.smart_plug_enabled" class="card plug">
    <div class="card-head"><h2><i class="fas fa-plug"></i>{{ t("Tester la prise") }}</h2></div>
    <div class="row">
      <button class="btn" type="button" :disabled="busy || !values.smart_plug_on_url" @click="test('smart_plug_on_url')"><i class="fas fa-power-off ok"></i>{{ t("Allumer la prise") }}</button>
      <button class="btn" type="button" :disabled="busy || !values.smart_plug_off_url" @click="test('smart_plug_off_url')"><i class="fas fa-power-off off"></i>{{ t("Éteindre la prise") }}</button>
    </div>
    <p v-if="status && status.status !== 'disabled'" class="small state"><span class="dot" :class="{ lit: on() }"></span>{{ status.message }}</p>
    <details class="small">
      <summary>{{ t("Exemples d'URLs :") }}</summary>
      <ul class="examples">
        <li><strong>Tasmota :</strong> <code>http://IP_PRISE/cm?cmnd=Power%20On</code></li>
        <li><strong>Shelly :</strong> <code>http://IP_PRISE/relay/0?turn=on</code></li>
        <li><strong>Home Assistant (webhook) :</strong> <code>http://IP_HA:8123/api/webhook/pimmich_on</code></li>
        <li><strong>{{ t("Statut Home Assistant :") }}</strong> <code>http://IP_HA:8123/api/states/sensor.pimmich_plug_status</code></li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.plug { margin-top: 1rem; }
.ok { color: var(--ok); } .off { color: var(--danger); }
.state { display: flex; align-items: center; gap: .5rem; margin-top: .6rem; }
.dot { width: 12px; height: 12px; border-radius: 50%; background: var(--muted); }
.dot.lit { background: var(--ok); }
details { margin-top: .6rem; }
summary { cursor: pointer; color: var(--accent); font-weight: 600; }
.examples { margin: .4rem 0 0; padding-left: 1.1rem; display: grid; gap: .25rem; }
code { background: var(--surface-2); padding: .1rem .35rem; border-radius: 6px; word-break: break-all; }
</style>
