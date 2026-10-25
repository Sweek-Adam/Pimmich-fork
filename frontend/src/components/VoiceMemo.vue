<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { post } from "../api";
import { t } from "../i18n";
import { notify, run } from "../toast";

// Souvenir vocal d'une photo : enregistré ici (micro du téléphone), lu par le cadre quand la photo passe
const props = defineProps<{ path: string; seconds: number | null | undefined }>();
const emit = defineEmits<{ (e: "changed", seconds: number | null): void }>();
const recording = ref(false);
const elapsed = ref(0);
const sending = ref(false);
const stamp = ref(Date.now());
const canRecord = window.isSecureContext && !!navigator.mediaDevices && "MediaRecorder" in window;
let recorder: MediaRecorder | null = null;
let timer: number | undefined;

async function upload(blob: Blob) {
  sending.value = true;
  const form = new FormData();
  form.append("path", props.path);
  form.append("voice", blob, "souvenir");
  try {
    const response = await fetch("/api/photo_voice", { method: "POST", body: form, credentials: "same-origin" });
    const r = await response.json();
    notify(r.message, !r.success);
    if (r.success) { stamp.value = Date.now(); emit("changed", r.seconds); }
  } catch (e) { notify((e as Error).message, true); } finally { sending.value = false; }
}
async function toggle() {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  let stream: MediaStream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch { notify(t("Micro inaccessible : autorisez-le dans le navigateur."), true); return; }
  const chunks: Blob[] = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = () => {
    stream.getTracks().forEach((track) => track.stop());
    window.clearInterval(timer);
    recording.value = false;
    upload(new Blob(chunks, { type: recorder?.mimeType || "audio/webm" }));
  };
  recorder.start();
  recording.value = true;
  elapsed.value = 0;
  const start = Date.now();
  timer = window.setInterval(() => {
    elapsed.value = Math.round((Date.now() - start) / 1000);
    if (elapsed.value >= 90) recorder?.stop();
  }, 250);
}
function pickFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (file) upload(file);
}
async function remove() {
  if (!window.confirm(t("Supprimer le souvenir vocal de cette photo ?"))) return;
  const r = await run(() => post("/api/photo_voice", { path: props.path }, "DELETE"));
  if (r) emit("changed", null);
}
watch(() => props.path, () => { if (recorder?.state === "recording") recorder.stop(); });
onUnmounted(() => { if (recorder?.state === "recording") recorder.stop(); window.clearInterval(timer); });
</script>

<template>
  <div class="memo">
    <template v-if="seconds">
      <audio :key="path + stamp" :src="`/api/photo_voice/listen?path=${encodeURIComponent(path)}&t=${stamp}`" controls preload="none"></audio>
      <button class="btn icon" type="button" :title="t('Supprimer le souvenir vocal')" @click="remove"><i class="fas fa-trash-alt"></i></button>
    </template>
    <button v-if="canRecord" class="btn" :class="{ rec: recording }" type="button" :disabled="sending" @click="toggle">
      <i class="fas" :class="recording ? 'fa-stop' : sending ? 'fa-spinner fa-spin' : 'fa-microphone'"></i>
      {{ recording ? t("Arrêter ({s} s)", { s: elapsed }) : seconds ? t("Raconter à nouveau") : t("Raconter cette photo") }}</button>
    <label v-else class="btn"><i class="fas fa-microphone"></i> {{ t("Raconter cette photo") }}
      <input type="file" accept="audio/*" capture hidden @change="pickFile"></label>
  </div>
</template>

<style scoped>
.memo { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; }
.memo audio { height: 34px; max-width: 220px; }
.rec { background: var(--danger); color: #fff; }
</style>
