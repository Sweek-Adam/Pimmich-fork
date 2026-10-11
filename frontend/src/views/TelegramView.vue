<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import SettingsPage from "../components/SettingsPage.vue";
import { get, post } from "../api";
import { boot } from "../boot";
import { currentLang, t } from "../i18n";
import type { Section } from "../settings";
import { notify, run } from "../toast";

interface Invitation { code: string; guest_name: string; expires_at: string; used_by_user_id: number | null; used_by_user_name?: string | null }

const status = ref<{ status: string; status_message: string } | null>(null);
const invitations = ref<Invitation[]>([]);
const guestName = ref("");
const duration = ref("7");
const botName = ref("");
let timer: number | undefined;

const sections = computed<Section[]>(() => [
  { title: () => t("Réception de photos par Telegram"), icon: "fa-paper-plane",
    intro: () => t("Pour créer un bot et obtenir un token, parlez à @BotFather sur Telegram. L'ID de l'administrateur est votre propre ID utilisateur Telegram (obtenu via @userinfobot par exemple)."),
    fields: [
      { key: "telegram_bot_enabled", label: () => t("Activer le bot de réception Telegram"), type: "toggle" },
      ...(boot.admin ? [
        { key: "telegram_bot_token", label: () => t("Token du Bot Telegram :"), type: "secret" as const },
        { key: "telegram_authorized_users", label: () => t("ID de l'administrateur"), type: "text" as const, placeholder: t("Votre ID numérique Telegram") },
      ] : []),
    ] },
  { title: () => t("Fréquence des Cartes Postales"), icon: "fa-envelope-open-text",
    fields: [
      { key: "telegram_boost_enabled", label: () => t("Activer le boost pour les cartes postales récentes"), type: "toggle" },
      { key: "telegram_boost_duration_days", label: () => t("Durée du boost (jours)"), type: "number", min: 1, max: 365, showIf: (v) => !!v.telegram_boost_enabled },
      { key: "telegram_boost_factor", label: () => t("Facteur de boost :"), type: "number", min: 0, max: 20, showIf: (v) => !!v.telegram_boost_enabled,
        help: () => t("(Ex: 4 = 5x plus de chances d'apparaître)") },
    ] },
]);

const statusClass = computed(() => ({ running: "ok", error: "warn" })[status.value?.status ?? ""] ?? "off");
const dateLabel = (iso: string) => new Date(iso).toLocaleDateString(currentLang(), { day: "numeric", month: "long", year: "numeric" });

async function loadStatus() {
  try { status.value = await get("/telegram_bot_status"); } catch { status.value = null; }
}

async function loadInvitations() {
  invitations.value = await get<Invitation[]>("/api/telegram/invitations");
}

async function testToken() {
  const d = await run(() => post<{ message: string }>("/test-telegram", {}));
  if (d) botName.value = d.message;
}

async function createInvitation() {
  if (!guestName.value.trim()) return notify(t("Le nom de l'invité est requis."), true);
  await run(() => post("/api/telegram/invitations", { name: guestName.value.trim(), duration: Number(duration.value) }), t("Invitation créée."));
  guestName.value = "";
  loadInvitations();
}

async function removeInvitation(inv: Invitation) {
  if (!window.confirm(t("Supprimer cette invitation ?"))) return;
  await run(() => post(`/api/telegram/invitations/${encodeURIComponent(inv.code)}`, {}, "DELETE"));
  loadInvitations();
}

async function revoke(inv: Invitation) {
  await run(() => post(`/api/telegram/invitations/${encodeURIComponent(inv.code)}/revoke`));
  loadInvitations();
}

async function copy(code: string) {
  try { await navigator.clipboard.writeText(code); notify(t("Copié.")); } catch { /* copie manuelle */ }
}

onMounted(() => {
  loadStatus();
  loadInvitations().catch(() => {});
  timer = window.setInterval(loadStatus, 10000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <section class="card status">
    <span class="pill" :class="statusClass"><span class="dot"></span>{{ t("État du bot :") }} {{ status?.status_message ?? "…" }}</span>
    <button v-if="boot.admin" class="btn small" type="button" @click="testToken"><i class="fas fa-vial"></i>{{ t("Tester le Token du Bot") }}</button>
  </section>
  <SettingsPage :sections="sections">
    <section class="card invitations">
      <div class="card-head"><h2><i class="fas fa-ticket-alt"></i>{{ t("Gestion des invitations pour les invités") }}</h2></div>
      <p class="small muted">{{ t("Créez des codes d'invitation uniques pour permettre à vos amis et votre famille d'envoyer des photos au cadre. Ils devront envoyer ce code à votre bot Telegram pour être autorisés.") }}</p>
      <form class="row create" @submit.prevent="createInvitation">
        <input v-model="guestName" type="text" class="spacer" :placeholder="t('Nom de l\'invité (ex: Mamie)')">
        <select v-model="duration">
          <option value="7">{{ t("Valide 7 jours") }}</option>
          <option value="30">{{ t("Valide 30 jours") }}</option>
          <option value="90">{{ t("Valide 90 jours") }}</option>
        </select>
        <button class="btn primary" type="submit"><i class="fas fa-plus"></i>{{ t("Créer") }}</button>
      </form>
      <h3>{{ t("Invitations actives") }}</h3>
      <p v-if="!invitations.length" class="small muted">{{ t("Aucune invitation active.") }}</p>
      <ul class="list">
        <li v-for="inv in invitations" :key="inv.code">
          <span class="spacer"><strong>{{ inv.guest_name }}</strong>
            <span class="small muted"> · {{ t("jusqu'au {date}", { date: dateLabel(inv.expires_at) }) }}</span>
            <br><span v-if="inv.used_by_user_id" class="small">{{ t("Utilisée par {name}", { name: inv.used_by_user_name || "?" }) }}</span>
            <button v-else type="button" class="code" :title="t('Copier')" @click="copy(inv.code)"><code>{{ inv.code }}</code> <i class="far fa-copy"></i></button></span>
          <button v-if="inv.used_by_user_id" class="btn small" type="button" @click="revoke(inv)">{{ t("Révoquer") }}</button>
          <button class="btn icon danger" type="button" :title="t('Supprimer')" @click="removeInvitation(inv)"><i class="fas fa-trash-alt"></i></button>
        </li>
      </ul>
      <p class="small muted">{{ botName }}</p>
    </section>
  </SettingsPage>
</template>

<style scoped>
.status { display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; margin-bottom: 1rem; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.invitations { margin-top: 1rem; }
.create { margin: .8rem 0 1rem; }
.create input, .create select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; min-width: 0; }
h3 { font-size: 1rem; margin-bottom: .4rem; }
.list { list-style: none; padding: 0; margin: 0; }
.list li { display: flex; align-items: center; gap: .5rem; padding: .5rem 0; border-bottom: 1px solid var(--border); }
.code { border: 0; background: var(--surface-2); color: var(--text); border-radius: 8px; padding: .1rem .5rem; margin-top: .2rem; cursor: pointer; font: inherit; }
.list .btn.icon { width: 2.2rem; height: 2.2rem; }
</style>
