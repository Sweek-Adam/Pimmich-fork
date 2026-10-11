<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import RadioCard from "../components/RadioCard.vue";
import SpotifyCard from "../components/SpotifyCard.vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

interface Sound {
  background_music: string; music_volume: number; now_playing_display: string; now_playing_position: string; jukebox_mode: string;
  files: string[]; receivers: Record<string, boolean>;
}
interface Slot { start: string; end: string; kind: string; value: string; label?: string }
interface Track { title: string; artist: string; cover?: string; source_label: string; playing: boolean }

const sound = ref<Sound | null>(null);
const schedule = reactive({ enabled: false, slots: [] as Slot[], stations: [] as { url: string; name: string }[], files: [] as string[], spotify: false });
const spotifyLists = ref<{ uri: string; name: string }[]>([]);
const music = ref<{ track: Track | null; actions: string[]; hint?: string } | null>(null);
const sleepLeft = ref<number | null>(null);
const bt = ref<{ available: boolean; discoverable: boolean; devices: { mac: string; name: string; connected: boolean }[]; service: boolean } | null>(null);
let timer: number | undefined;

const kinds = computed(() => ({ radio: t("Radio"), file: t("Musique du cadre"), spotify: "Spotify" } as Record<string, string>));
const icons: Record<string, string> = { previous: "fa-step-backward", pause: "fa-pause", play: "fa-play", next: "fa-step-forward" };

async function loadSound() { sound.value = await get<Sound>("/api/sound"); }
async function saveSound(change: Partial<Sound>) {
  const done = await run(() => post("/api/sound", change));
  if (done && sound.value) Object.assign(sound.value, change);
}
async function uploadMusic(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append("music_file", file);
  try {
    const r = await (await fetch("/api/upload_music", { method: "POST", body: form, credentials: "same-origin" })).json();
    notify(r.message, !r.success);
  } catch (e) { notify((e as Error).message, true); }
  loadSound();
}

async function loadSchedule() {
  const d = await get<{ enabled: boolean; slots: Slot[]; stations: { url: string; name: string }[]; files: string[]; spotify: boolean }>("/api/music/schedule");
  Object.assign(schedule, d);
  if (!schedule.slots.length) schedule.slots = [{ start: "07:00", end: "10:00", kind: "radio", value: "" }, { start: "18:00", end: "21:00", kind: "radio", value: "" }];
  if (d.spotify) get<{ playlists: { uri: string; name: string }[] }>("/api/spotify/playlists").then((r) => (spotifyLists.value = r.playlists)).catch(() => {});
}
function slotOptions(kind: string) {
  if (kind === "radio") return schedule.stations.map((s) => ({ value: s.url, label: s.name }));
  if (kind === "file") return schedule.files.map((f) => ({ value: f, label: f }));
  return spotifyLists.value.map((p) => ({ value: p.uri, label: p.name }));
}
async function saveSchedule() {
  const slots = schedule.slots.filter((s) => s.value).map((s) => ({ ...s, label: slotOptions(s.kind).find((o) => o.value === s.value)?.label ?? "" }));
  await run(() => post("/api/music/schedule", { enabled: schedule.enabled, slots }));
}

async function refreshMusic() {
  try { music.value = await get("/api/music/remote"); } catch { music.value = null; }
  try { sleepLeft.value = (await get<{ remaining: number | null }>("/api/music/sleep")).remaining; } catch { sleepLeft.value = null; }
}
async function musicAction(action: string) { await run(() => post("/api/music/remote", { action })); window.setTimeout(refreshMusic, 700); }
async function setSleep(minutes: number) {
  const d = await run(() => post<{ remaining: number | null; message: string }>("/api/music/sleep", { minutes }));
  if (d) sleepLeft.value = d.remaining;
}

async function loadBluetooth() { try { bt.value = await get("/api/bluetooth"); } catch { bt.value = null; } }
async function pair() { await run(() => post("/api/bluetooth/pair")); window.setTimeout(loadBluetooth, 1500); }
async function forget(mac: string) { await run(() => post("/api/bluetooth/forget", { mac })); loadBluetooth(); }

onMounted(() => {
  loadSound().catch(() => {});
  loadSchedule().catch(() => {});
  refreshMusic();
  loadBluetooth();
  timer = window.setInterval(() => { refreshMusic(); loadBluetooth(); }, 8000);
});
onUnmounted(() => window.clearInterval(timer));
</script>

<template>
  <div class="grid grid-2 top">
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-music"></i>{{ t("Musique du diaporama") }}</h2></div>
      <p class="small muted">{{ t("Jouée en boucle pendant le diaporama. Chaque playlist peut avoir sa propre musique (rubrique Playlists).") }}</p>
      <template v-if="sound">
        <label class="field">{{ t("Musique") }}
          <select :value="sound.background_music" @change="saveSound({ background_music: ($event.target as HTMLSelectElement).value })">
            <option value="">{{ t("Aucune musique") }}</option>
            <option v-for="f in sound.files" :key="f" :value="f">{{ f }}</option>
          </select></label>
        <audio v-if="sound.background_music" :src="`/static/music/${encodeURIComponent(sound.background_music)}`" controls class="preview"></audio>
        <label class="field">{{ t("Volume") }} : {{ sound.music_volume }} %
          <input type="range" min="0" max="100" step="5" :value="sound.music_volume" @change="saveSound({ music_volume: Number(($event.target as HTMLInputElement).value) })"></label>
        <label class="btn upload"><i class="fas fa-upload"></i>{{ t("Ajouter une musique (MP3, WAV)") }}
          <input type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" hidden @change="uploadMusic"></label>
      </template>
    </section>

    <section class="card">
      <div class="card-head"><h2><i class="fas fa-headphones"></i>{{ t("Musique en cours") }}</h2></div>
      <div v-if="music?.track" class="now">
        <img v-if="music.track.cover" :src="music.track.cover" alt="">
        <div class="spacer">
          <p class="small muted">{{ music.track.source_label }}</p>
          <strong>{{ music.track.title }}</strong>
          <p class="muted">{{ music.track.artist }}</p>
          <div class="row">
            <button v-for="a in music.actions" :key="a" class="btn icon" type="button" @click="musicAction(a)"><i class="fas" :class="icons[a] || 'fa-music'"></i></button>
          </div>
          <p v-if="!music.actions.length && music.hint" class="small muted">{{ music.hint }}</p>
        </div>
      </div>
      <p v-else class="muted">{{ t("Aucune musique en cours.") }}</p>
      <label class="field sleep"><span><i class="fas fa-moon"></i> {{ t("Minuteur de sommeil") }}</span>
        <select :value="0" @change="setSleep(Number(($event.target as HTMLSelectElement).value))">
          <option value="0">{{ t("Arrêter la musique…") }}</option>
          <option value="15">{{ t("dans 15 min") }}</option>
          <option value="30">{{ t("dans 30 min") }}</option>
          <option value="60">{{ t("dans 1 h") }}</option>
          <option value="90">{{ t("dans 1 h 30") }}</option>
        </select>
        <small v-if="sleepLeft" class="muted">{{ t("Arrêt dans {n} min", { n: Math.ceil(sleepLeft / 60) }) }}</small></label>
      <template v-if="sound">
        <label class="field">{{ t("Afficher le morceau sur le cadre") }}
          <select :value="sound.now_playing_display" @change="saveSound({ now_playing_display: ($event.target as HTMLSelectElement).value })">
            <option value="change">{{ t("Quelques secondes à chaque nouveau morceau") }}</option>
            <option value="always">{{ t("En permanence pendant la lecture") }}</option>
            <option value="off">{{ t("Ne pas afficher") }}</option>
          </select></label>
        <label class="field">{{ t("Position") }}
          <select :value="sound.now_playing_position" @change="saveSound({ now_playing_position: ($event.target as HTMLSelectElement).value })">
            <option value="bottom_left">{{ t("En bas à gauche") }}</option>
            <option value="bottom_right">{{ t("En bas à droite") }}</option>
            <option value="top_left">{{ t("En haut à gauche") }}</option>
            <option value="top_right">{{ t("En haut à droite") }}</option>
          </select></label>
        <label class="field">{{ t("Pendant Spotify, AirPlay, Bluetooth ou la radio :") }}
          <select :value="sound.jukebox_mode" @change="saveSound({ jukebox_mode: ($event.target as HTMLSelectElement).value })">
            <option value="off">{{ t("Les photos continuent") }}</option>
            <option value="jukebox">{{ t("Jukebox : la pochette en grand à l'écran") }}</option>
            <option value="karaoke">{{ t("Karaoké : les paroles défilent en rythme (Spotify)") }}</option>
          </select></label>
      </template>
    </section>
  </div>

  <section class="card">
    <div class="card-head"><h2><i class="fas fa-clock"></i>{{ t("Musique selon l'heure") }}</h2></div>
    <p class="small muted">{{ t("Une ambiance par moment de la journée : calme le matin, festive le soir… Au début de chaque plage, le cadre lance sa musique ; il ne coupe jamais une musique lancée à la main.") }}</p>
    <label class="check"><input v-model="schedule.enabled" type="checkbox" class="switch"><strong>{{ t("Activer la musique selon l'heure") }}</strong></label>
    <div v-for="(slot, i) in schedule.slots" :key="i" class="slot">
      <input v-model="slot.start" type="time"><input v-model="slot.end" type="time">
      <select v-model="slot.kind"><option v-for="(label, key) in kinds" :key="key" :value="key">{{ label }}</option></select>
      <select v-model="slot.value" class="spacer">
        <option value="" disabled>{{ slotOptions(slot.kind).length ? t("Choisir…") : slot.kind === "spotify" ? t("Connectez Spotify (plus bas) pour choisir une playlist.") : "—" }}</option>
        <option v-for="o in slotOptions(slot.kind)" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <button class="btn icon danger" type="button" :title="t('Retirer')" @click="schedule.slots.splice(i, 1)"><i class="fas fa-times"></i></button>
    </div>
    <div class="row">
      <button class="btn" type="button" @click="schedule.slots.push({ start: '12:00', end: '14:00', kind: 'radio', value: '' })"><i class="fas fa-plus"></i>{{ t("Ajouter une plage") }}</button>
      <button class="btn primary" type="button" @click="saveSchedule"><i class="fas fa-check"></i>{{ t("Enregistrer") }}</button>
    </div>
  </section>

  <RadioCard />
  <SpotifyCard />

  <section class="card speaker">
    <div class="card-head"><h2><i class="fas fa-volume-up"></i>{{ t("Le cadre comme enceinte") }}</h2></div>
    <div class="receivers">
      <div><h3><i class="fab fa-spotify"></i> Spotify Connect <span class="pill" :class="sound?.receivers.spotify ? 'ok' : 'off'">{{ sound?.receivers.spotify ? t("Actif") : t("Non installé") }}</span></h3>
        <p class="small muted">{{ t("Dans l'application Spotify, choisissez « Cadre photo » comme appareil : la musique sort par l'écran du cadre. Compte Spotify Premium nécessaire.") }}</p></div>
      <div><h3><i class="fab fa-apple"></i> AirPlay <span class="pill" :class="sound?.receivers.airplay ? 'ok' : 'off'">{{ sound?.receivers.airplay ? t("Actif") : t("Non installé") }}</span></h3>
        <p class="small muted">{{ t("Depuis un iPhone, un iPad ou un Mac, envoyez le son de n'importe quelle application (Deezer, Apple Music, YouTube...) vers « Cadre photo ».") }}</p></div>
      <div><h3><i class="fab fa-bluetooth-b"></i> Bluetooth <span class="pill" :class="sound?.receivers.bluetooth ? 'ok' : 'off'">{{ sound?.receivers.bluetooth ? t("Actif") : t("Non installé") }}</span></h3>
        <p class="small muted">{{ t("Pour les téléphones Android (Deezer, YouTube Music...) : associez une fois le téléphone, il se reconnecte ensuite tout seul. Le cadre n'accepte un nouvel appareil que pendant 3 minutes après un appui sur « Associer un téléphone ».") }}</p>
        <template v-if="sound?.receivers.bluetooth">
          <button class="btn" type="button" @click="pair"><i class="fab fa-bluetooth-b"></i>{{ t("Associer un téléphone") }}</button>
          <p v-if="bt?.discoverable" class="small">{{ t("Visible : choisissez « Cadre photo » sur le téléphone") }}</p>
          <ul class="devices">
            <li v-for="d in bt?.devices || []" :key="d.mac"><span class="spacer">{{ d.name }}<template v-if="d.connected"> · {{ t("connecté") }}</template></span>
              <button class="btn small" type="button" @click="forget(d.mac)">{{ t("Oublier") }}</button></li>
            <li v-if="bt && !bt.devices.length" class="muted small">{{ t("Aucun téléphone associé.") }}</li>
          </ul>
        </template>
      </div>
    </div>
    <p v-if="sound && !(sound.receivers.spotify && sound.receivers.airplay && sound.receivers.bluetooth)" class="small muted">
      {{ t("Pour activer ces fonctions, lancez une fois sur le Raspberry Pi :") }} <code>sudo ~/pimmich/utils/enable_music_receivers.sh</code></p>
  </section>
</template>

<style scoped>
.top { margin-bottom: 1rem; }
.top .card + .card { margin-top: 0; }
.field { display: grid; gap: .25rem; font-weight: 600; font-size: .9rem; margin-top: .7rem; }
.field select { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; }
.field input[type="range"] { accent-color: var(--accent); }
.preview { width: 100%; margin-top: .6rem; }
.upload { margin-top: .8rem; }
.now { display: flex; gap: .8rem; align-items: center; }
.now img { width: 80px; height: 80px; border-radius: 10px; object-fit: cover; }
.sleep span i { color: var(--accent); }
.check { display: flex; align-items: center; gap: .7rem; margin: .8rem 0; }
.slot { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; margin-bottom: .4rem; }
.slot input, .slot select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .35rem .5rem; min-width: 0; }
.slot .btn.icon { width: 2.2rem; height: 2.2rem; }
.speaker { margin-top: 1rem; }
.receivers { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }
.receivers h3 { font-size: 1rem; display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; margin-bottom: .3rem; }
.devices { list-style: none; padding: 0; margin: .5rem 0 0; }
.devices li { display: flex; gap: .5rem; align-items: center; padding: .3rem 0; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
code { background: var(--surface-2); padding: .1rem .4rem; border-radius: 6px; }
</style>
