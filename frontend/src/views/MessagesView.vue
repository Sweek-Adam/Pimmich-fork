<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { ApiError, get, post } from "../api";
import QuoteCard from "../components/QuoteCard.vue";
import { currentLang, t } from "../i18n";
import { notify, run } from "../toast";

interface Message {
  id: string; title: string; body: string; signature: string; style: string; kind?: string; created: string;
  author: string; guest?: boolean; hidden?: boolean; on_air?: boolean; expires?: string | null;
  schedule?: { starts: string; repeat: string; duration_hours: number } | null;
}

const messages = ref<Message[] | null>(null);
const styles = ref<Record<string, string>>({});
const form = reactive({ title: "", body: "", signature: "", style: "", expires: "", schedule: false, starts: "", repeat: "none", duration_hours: 24 });
const preview = ref<string | null>(null);
const publishing = ref(false);
const expiresEdit = reactive<Record<string, string>>({});

const repeatLabels = computed<Record<string, string>>(() => ({
  none: "", daily: t("chaque jour"), weekly: t("chaque semaine"), monthly: t("chaque mois"), yearly: t("chaque année"),
}));

function payload() {
  return {
    title: form.title, body: form.body, signature: form.signature, style: form.style, expires: form.expires || null,
    starts: form.schedule && form.starts ? form.starts : null, repeat: form.repeat, duration_hours: Number(form.duration_hours),
  };
}

async function load() {
  const d = await get<{ messages: Message[]; styles: Record<string, string> }>("/api/messages");
  messages.value = d.messages;
  styles.value = d.styles;
  if (!form.style) form.style = Object.keys(d.styles)[0] ?? "";
  for (const m of d.messages) expiresEdit[m.id] = m.expires || "";
}

async function showPreview() {
  try {
    const response = await fetch("/api/messages/preview", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()), credentials: "same-origin",
    });
    if (!response.ok) throw new ApiError((await response.json()).message, response.status);
    if (preview.value) URL.revokeObjectURL(preview.value);
    preview.value = URL.createObjectURL(await response.blob());
  } catch (e) {
    notify((e as Error).message, true);
  }
}

async function publish() {
  publishing.value = true;
  const done = await run(() => post("/api/messages", payload()));
  publishing.value = false;
  if (done) {
    Object.assign(form, { title: "", body: "", signature: "", expires: "", starts: "", schedule: false });
    preview.value = null;
    load();
  }
}

const imageOf = (m: Message) =>
  `/static/${m.hidden || m.on_air === false ? "messages_hidden" : "prepared/messages"}/${m.id}.jpg?v=${encodeURIComponent(m.created)}`;

function scheduleText(m: Message) {
  if (!m.schedule) return "";
  const start = new Date(m.schedule.starts);
  const day = start.toLocaleDateString(currentLang(), { day: "numeric", month: "short" });
  const time = start.toLocaleTimeString(currentLang(), { hour: "2-digit", minute: "2-digit" });
  const repeat = repeatLabels.value[m.schedule.repeat];
  return `⏰ ${day} ${time}${repeat ? " · " + repeat : ""}`;
}

async function saveExpires(m: Message) {
  await run(() => post(`/api/messages/${m.id}/expires`, { expires: expiresEdit[m.id] || null }));
  load();
}

async function toggleHidden(m: Message) {
  await run(() => post(`/api/messages/${m.id}/visibility`, { hidden: !m.hidden }));
  load();
}

async function remove(m: Message) {
  if (!window.confirm(t("Supprimer ce message ?"))) return;
  await run(() => post(`/api/messages/${m.id}`, {}, "DELETE"));
  load();
}

onMounted(load);
onUnmounted(() => { if (preview.value) URL.revokeObjectURL(preview.value); });
</script>

<template>
  <div class="grid grid-2 compose">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-pen-fancy"></i>{{ t("Écrire un message") }}</h2></div>
      <p class="small muted">{{ t("Le message est transformé en image et s'affiche dans le diaporama comme une photo.") }}</p>
      <form class="fields" @submit.prevent="publish">
        <label>{{ t("Titre (optionnel)") }}<input v-model="form.title" type="text" :placeholder="t('ex : Joyeux anniversaire !')"></label>
        <label>{{ t("Message") }}<textarea v-model="form.body" rows="4" :placeholder="t('Votre texte…')"></textarea></label>
        <label>{{ t("Signature (optionnelle)") }}<input v-model="form.signature" type="text" :placeholder="t('ex : Toute la famille')"></label>
        <div class="two">
          <label>{{ t("Style") }}
            <select v-model="form.style"><option v-for="(label, key) in styles" :key="key" :value="key">{{ label }}</option></select></label>
          <label>{{ t("Afficher jusqu'au (optionnel)") }}<input v-model="form.expires" type="date"></label>
        </div>
        <label class="check"><input v-model="form.schedule" type="checkbox">{{ t("Programmer (ex : le 12 mars à 8 h, chaque année)") }}</label>
        <div v-if="form.schedule" class="three">
          <label>{{ t("À partir du") }}<input v-model="form.starts" type="datetime-local"></label>
          <label>{{ t("Répéter") }}
            <select v-model="form.repeat">
              <option value="none">{{ t("Une seule fois") }}</option>
              <option value="daily">{{ t("Chaque jour") }}</option>
              <option value="weekly">{{ t("Chaque semaine") }}</option>
              <option value="monthly">{{ t("Chaque mois") }}</option>
              <option value="yearly">{{ t("Chaque année") }}</option>
            </select></label>
          <label>{{ t("Affiché pendant") }}
            <select v-model.number="form.duration_hours">
              <option :value="1">{{ t("1 heure") }}</option>
              <option :value="3">{{ t("3 heures") }}</option>
              <option :value="12">{{ t("12 heures") }}</option>
              <option :value="24">{{ t("1 jour") }}</option>
              <option :value="72">{{ t("3 jours") }}</option>
              <option :value="168">{{ t("1 semaine") }}</option>
            </select></label>
        </div>
        <div class="row">
          <button class="btn" type="button" @click="showPreview"><i class="fas fa-eye"></i>{{ t("Aperçu") }}</button>
          <button class="btn primary" type="submit" :disabled="publishing || !(form.body.trim() || form.title.trim())"><i class="fas fa-paper-plane"></i>{{ t("Publier") }}</button>
        </div>
      </form>
    </section>
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-tv"></i>{{ t("Aperçu à l'écran") }}</h2></div>
      <img v-if="preview" :src="preview" :alt="t('Aperçu du message')" class="preview">
      <p v-else class="muted">{{ t("Cliquez sur « Aperçu » pour voir le rendu.") }}</p>
    </section>
  </div>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-comment-alt"></i>{{ t("Messages") }}</h2></div>
    <div v-if="!messages" class="skeleton" style="height: 160px"></div>
    <p v-else-if="!messages.length" class="muted">{{ t("Aucun message pour l'instant.") }}</p>
    <div v-else class="list">
      <article v-for="m in messages" :key="m.id" class="message" :class="{ hidden: m.hidden }">
        <img :src="imageOf(m)" :alt="m.title || m.body" loading="lazy">
        <div class="meta">
          <span v-if="m.guest" class="pill info">{{ t("Invité") }}</span>
          <span v-if="m.hidden" class="pill off">{{ t("Masqué") }}</span>
          <span v-if="m.schedule" class="pill warn">{{ scheduleText(m) }}</span>
          <span class="small muted">{{ m.created }}<template v-if="m.author"> · {{ m.author }}</template></span>
        </div>
        <div class="row until">
          <span class="small">{{ t("Jusqu'au :") }}</span>
          <input v-model="expiresEdit[m.id]" type="date" :title="t('Laisser vide pour afficher sans limite')">
          <button v-if="(expiresEdit[m.id] || '') !== (m.expires || '')" class="btn icon primary" type="button" :title="t('Enregistrer la date de fin')" @click="saveExpires(m)"><i class="fas fa-check"></i></button>
          <span class="spacer"></span>
          <button class="btn icon" type="button" :title="m.hidden ? t('Afficher de nouveau dans le diaporama') : t('Masquer du diaporama sans supprimer')" @click="toggleHidden(m)">
            <i class="fas" :class="m.hidden ? 'fa-eye' : 'fa-eye-slash'"></i></button>
          <button class="btn icon danger" type="button" :title="t('Supprimer ce message')" @click="remove(m)"><i class="fas fa-trash-alt"></i></button>
        </div>
      </article>
    </div>
  </section>
  <QuoteCard />
</template>

<style scoped>
.compose { margin-bottom: 1rem; }
.compose .card + .card { margin-top: 0; }
.fields { display: grid; gap: .7rem; margin-top: .8rem; }
.fields label { display: grid; gap: .25rem; font-weight: 600; font-size: .9rem; }
.fields input, .fields select, .fields textarea { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .5rem .7rem; }
.fields textarea { resize: vertical; }
.fields .check { display: flex; align-items: center; gap: .5rem; font-weight: 500; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; }
.three { display: grid; grid-template-columns: repeat(3, 1fr); gap: .7rem; }
@media (max-width: 640px) { .two, .three { grid-template-columns: 1fr; } }
.preview { width: 100%; border-radius: 10px; }
.links { margin-top: .8rem; }
.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: .9rem; }
.message { border: 1px solid var(--border); border-radius: 14px; overflow: hidden; background: var(--surface); }
.message.hidden { opacity: .6; }
.message img { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; background: var(--surface-2); }
.meta { display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; padding: .6rem .7rem 0; }
.pill.info { background: var(--accent-soft); color: var(--accent); }
.until { padding: .5rem .7rem .7rem; flex-wrap: nowrap; }
.until input { font: inherit; font-size: .85rem; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: .25rem .4rem; min-width: 0; }
.until .btn.icon { width: 2.1rem; height: 2.1rem; flex: none; }
</style>
