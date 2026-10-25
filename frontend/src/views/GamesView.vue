<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import SettingsPage from "../components/SettingsPage.vue";
import { get, post } from "../api";
import { t } from "../i18n";
import type { Section } from "../settings";
import { values } from "../settings";
import { run } from "../toast";

interface Status {
  phase: string; left: number; mode: string | null; mode_label: string; total: number; number?: number; question?: string;
  answer?: unknown; answered?: number; voted?: number; players?: { name: string; score?: number; checked?: number }[]; winners?: string[];
}

const modes = ref<{ key: string; label: string }[]>([]);
const mode = ref("classique");
const rounds = ref<number>(6);
const status = ref<Status | null>(null);
const gameUrl = `http://${location.hostname}/jeu`;

const DESCRIPTIONS: Record<string, () => string> = {
  classique: () => t("Deviner l'année, le lieu ou qui a envoyé la photo."),
  avant_apres: () => t("Deux photos : laquelle est la plus ancienne ?"),
  zoom: () => t("La photo se dézoome peu à peu : répondre tôt rapporte plus."),
  puzzle: () => t("Les pièces se remettent en place peu à peu : répondre tôt rapporte plus."),
  ligne: () => t("Remettre 4 photos dans l'ordre, de la plus ancienne à la plus récente."),
  qui: () => t("Qui est sur la photo floutée ? (personnes reconnues par Immich)"),
  legende: () => t("Chacun écrit la légende la plus drôle, puis tout le monde vote."),
  defi: () => t("Un défi (« quelque chose de bleu »...) : chacun prend une photo, puis tout le monde vote."),
  memoire: () => t("6 photos à retenir, puis : laquelle n'y était pas ?"),
  proche: () => t("Des nombres à deviner sur vos photos : le plus proche gagne."),
  melange: () => t("Un peu de chaque jeu."),
  bingo: () => t("Une grille sur chaque téléphone pendant le diaporama : la première ligne complète gagne."),
};
const PHASES: Record<string, () => string> = {
  lobby: () => t("Salle d'attente"), memorize: () => t("Photos à retenir"), question: () => t("Question"), vote: () => t("Vote"),
  reveal: () => t("Réponse"), podium: () => t("Podium"), bingo: () => t("Bingo en cours"), over: () => t("Aucune partie"),
};

const sections: Section[] = [
  { title: () => t("Temps de jeu"), icon: "fa-stopwatch",
    intro: () => t("Les temps sont pris en compte pour la prochaine partie (une partie en cours garde les siens)."),
    fields: [
      { key: "game_question_seconds", label: () => t("Temps pour répondre"), type: "range", min: 5, max: 120, step: 5, unit: " s" },
      { key: "game_reveal_seconds", label: () => t("Affichage de la réponse et des points"), type: "range", min: 3, max: 30, step: 1, unit: " s" },
      { key: "game_memorize_seconds", label: () => t("Mémoire : temps pour retenir les photos"), type: "range", min: 3, max: 60, step: 1, unit: " s" },
      { key: "game_timeline_seconds", label: () => t("Ligne du temps : temps pour remettre dans l'ordre"), type: "range", min: 10, max: 180, step: 5, unit: " s" },
      { key: "game_caption_seconds", label: () => t("Légende la plus drôle : temps pour écrire"), type: "range", min: 10, max: 300, step: 10, unit: " s" },
      { key: "game_challenge_seconds", label: () => t("Défi photo : temps pour prendre la photo"), type: "range", min: 30, max: 900, step: 30, unit: " s" },
      { key: "game_vote_seconds", label: () => t("Temps pour voter"), type: "range", min: 5, max: 180, step: 5, unit: " s" },
      { key: "game_podium_seconds", label: () => t("Affichage du podium final"), type: "range", min: 5, max: 120, step: 5, unit: " s" },
      { key: "game_lobby_minutes", label: () => t("Salle d'attente abandonnée après"), type: "range", min: 1, max: 60, step: 1, unit: " min" },
      { key: "game_bingo_minutes", label: () => t("Durée d'un bingo"), type: "range", min: 5, max: 240, step: 5, unit: " min" },
    ] },
  { title: () => t("Règles"), icon: "fa-sliders-h", fields: [
    { key: "family_game_enabled", label: () => t("Autoriser les jeux (page /jeu, depuis le Wi-Fi de la maison)"), type: "toggle" },
    { key: "game_rounds", label: () => t("Nombre de questions par défaut"), type: "range", min: 1, max: 15, step: 1 },
    { key: "game_auto_reveal", label: () => t("Dès que tout le monde a répondu (ou voté), afficher la réponse sans attendre"), type: "toggle" },
    { key: "game_speed_bonus", label: () => t("Bonus de vitesse (zoom, puzzle, flou : répondre tôt rapporte plus)"), type: "toggle" },
    { key: "game_max_players", label: () => t("Nombre maximum de joueurs"), type: "range", min: 2, max: 50, step: 1 },
    { key: "game_keep_challenge_photos", label: () => t("Garder les photos du défi (album de la fête, ou source « jeux »)"), type: "toggle",
      help: () => t("Sinon, elles sont effacées à la fin de la partie.") },
  ] },
];

const playing = computed(() => !!status.value && status.value.phase !== "over");
const description = computed(() => DESCRIPTIONS[mode.value]?.() ?? "");
const showAnswer = (a: unknown) => (typeof a === "string" && /^[A-D]{4}$/.test(a) ? a.split("").join(" → ") : String(a ?? ""));

async function loadStatus() {
  try { status.value = await get<Status>("/api/game/status"); } catch { /* hors ligne : on réessaie */ }
}
async function launch() {
  const r = await run(() => post("/jeu/new", { mode: mode.value, rounds: rounds.value }));
  if (r?.success) loadStatus();
}
const action = (url: string) => async () => { await run(() => post(url)); loadStatus(); };
const startGame = action("/api/game/start");
const skip = action("/api/game/skip");
async function stopGame() {
  if (!window.confirm(t("Arrêter la partie ? Le diaporama reprend."))) return;
  await action("/api/game/stop")();
}

let timer: number | undefined;
onMounted(async () => {
  get<{ modes: { key: string; label: string }[] }>("/jeu/modes").then((d) => (modes.value = d.modes)).catch(() => {});
  await loadStatus();
  rounds.value = Number(values.game_rounds ?? 6) || 6;
  timer = window.setInterval(loadStatus, 2000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <div class="grid grid-2 top">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-dice"></i>{{ t("Lancer une partie") }}</h2></div>
      <label class="field">{{ t("Jeu") }}
        <select v-model="mode"><option v-for="m in modes" :key="m.key" :value="m.key">{{ m.label }}</option></select></label>
      <p class="small muted">{{ description }}</p>
      <label v-if="mode !== 'bingo'" class="field">{{ t("Nombre de questions") }}
        <input v-model.number="rounds" type="number" min="1" max="15"></label>
      <div class="row">
        <button class="btn primary" type="button" :disabled="playing && status?.phase !== 'bingo'" @click="launch"><i class="fas fa-play"></i>{{ t("Lancer") }}</button>
        <a class="btn" :href="gameUrl" target="_blank"><i class="fas fa-mobile-alt"></i>{{ t("Ouvrir la page des joueurs") }}</a>
      </div>
      <p class="small muted">{{ t("Les joueurs scannent le QR code affiché sur le cadre, ou ouvrent :") }} <code>{{ gameUrl }}</code></p>
    </section>

    <section class="card live" :class="{ on: playing }">
      <div class="card-head"><h2><i class="fas fa-broadcast-tower"></i>{{ t("Partie en cours") }}</h2>
        <span v-if="status" class="pill" :class="playing ? 'ok' : 'off'">{{ PHASES[status.phase]?.() ?? status.phase }}</span></div>
      <template v-if="status && playing">
        <p><strong>{{ status.mode_label }}</strong>
          <span v-if="status.number"> · {{ t("Question {n}/{total}", { n: status.number, total: status.total }) }}</span>
          <span v-if="status.left && status.phase !== 'lobby'"> · {{ status.phase === "bingo" ? t("encore {m} min", { m: Math.round(status.left / 60) }) : `${status.left} s` }}</span></p>
        <p v-if="status.question" class="small">{{ status.question }}</p>
        <p v-if="status.answer !== undefined && status.answer !== null" class="small muted">{{ t("Réponse :") }} <strong>{{ showAnswer(status.answer) }}</strong>
          · {{ t("{n} réponse(s)", { n: status.answered ?? 0 }) }}<span v-if="status.voted"> · {{ t("{n} vote(s)", { n: status.voted }) }}</span></p>
        <ol v-if="status.players?.length" class="players">
          <li v-for="p in status.players" :key="p.name"><span>{{ p.name }}</span>
            <strong v-if="p.score !== undefined">{{ p.score }} pts</strong><strong v-else>{{ t("{n} case(s)", { n: p.checked ?? 0 }) }}</strong></li>
        </ol>
        <p v-else class="small muted">{{ t("Aucun joueur pour l'instant.") }}</p>
        <p v-if="status.winners?.length" class="small">🎉 {{ status.winners.join(", ") }}</p>
        <div class="row">
          <button v-if="status.phase === 'lobby'" class="btn primary" type="button" :disabled="!status.players?.length" @click="startGame"><i class="fas fa-play"></i>{{ t("Commencer") }}</button>
          <button v-if="!['lobby', 'bingo', 'podium'].includes(status.phase)" class="btn" type="button" @click="skip"><i class="fas fa-forward"></i>{{ t("Passer") }}</button>
          <button class="btn danger" type="button" @click="stopGame"><i class="fas fa-stop"></i>{{ t("Arrêter") }}</button>
        </div>
      </template>
      <p v-else class="muted">{{ t("Aucune partie en cours. Lancez-en une à gauche, ou depuis un téléphone sur la page /jeu.") }}</p>
    </section>
  </div>

  <SettingsPage :sections="sections" />
</template>

<style scoped>
.top { margin-bottom: 1rem; }
.field { display: grid; gap: .3rem; margin: .5rem 0; }
.row { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .6rem; }
.live.on { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }
.players { margin: .5rem 0 0; padding-left: 1.4rem; display: grid; gap: .25rem; }
.players li span { display: inline-block; min-width: 50%; }
</style>
