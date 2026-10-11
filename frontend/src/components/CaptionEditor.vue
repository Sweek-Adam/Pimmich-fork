<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { notify } from "../toast";

// Style d'une légende : mêmes champs que utils/captions.py (aperçu dessiné par le cadre lui-même)
type Style = Record<string, string | number | boolean>;
interface CaptionData {
  styles: Record<string, Style>; media_style: Style | null; presets: Record<string, Style>; defaults: Record<string, Style>; samples: Record<string, string>;
}

const props = defineProps<{ scope: string; photo?: string | null; text?: string }>();
const emit = defineEmits<{ close: []; saved: [] }>();

const SWATCHES = ["#ffffff", "#000000", "#111111", "#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be", "#007aff", "#5856d6", "#ff2d55", "#ff3fd2", "#a2845e", "#505050"];
const data = ref<CaptionData | null>(null);
const state = reactive<Style>({});
const sample = ref(props.text || "");
const preview = ref("");
const busy = ref(false);
const stage = ref<HTMLElement | null>(null);
const image = ref<HTMLImageElement | null>(null);
let timer: number | undefined;
let seq = 0;
let dragging = false;

const media = computed(() => !!props.photo);
const scopeKey = computed(() => (media.value ? "photo" : props.scope));
const title = computed(() => (media.value ? t("Style de cette légende") : {
  photo: t("Légendes des photos et vidéos"), polaroid: t("Texte des polaroïds"), metadata: t("Infos des photos (date, lieu)"),
}[props.scope] ?? ""));
const presets = computed(() => [["classic", t("Classique")], ["big", t("Grand texte")], ["bubble", t("Bulle")], ["label", t("Étiquette")], ["handwritten", t("Manuscrit")], ["neon", t("Néon")]]);
const fonts = computed(() => [["caveat", "Caveat"], ["patrick", "Patrick Hand"], ["marker", "Permanent Marker"], ["elite", "Special Elite"], ["sans", t("Moderne")], ["serif", t("Classique (empattements)")]]);
const backgrounds = computed(() => [["none", t("Aucun")], ["band", t("Bandeau")], ["bubble", t("Bulle")], ["box", t("Étiquette")]]);
const shadows = computed(() => [["none", t("Aucun")], ["drop", t("Ombre")], ["glow", t("Halo lumineux")]]);

function render() {
  window.clearTimeout(timer);
  timer = window.setTimeout(async () => {
    const mine = ++seq;
    busy.value = true;
    try {
      const response = await fetch("/api/captions/preview", {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
        body: JSON.stringify({ scope: scopeKey.value, style: { ...state }, text: sample.value, photo: props.photo }),
      });
      const url = URL.createObjectURL(await response.blob());
      if (mine !== seq) return URL.revokeObjectURL(url);
      if (preview.value) URL.revokeObjectURL(preview.value);
      preview.value = url;
    } finally {
      if (mine === seq) busy.value = false;
    }
  }, 220);
}

function set(field: string, value: string | number | boolean) {
  state[field] = value;
  render();
}

function apply(style: Style) {
  for (const key of Object.keys(state)) delete state[key];
  Object.assign(state, style);
  render();
}

function moveTo(event: PointerEvent) {
  const box = image.value?.getBoundingClientRect();
  if (!box) return;
  state.x = Math.round(Math.min(100, Math.max(0, ((event.clientX - box.left) / box.width) * 100)));
  state.y = Math.round(Math.min(100, Math.max(0, ((event.clientY - box.top) / box.height) * 100)));
}
function down(event: PointerEvent) {
  if (scopeKey.value === "polaroid") return;
  dragging = true;
  stage.value?.setPointerCapture(event.pointerId);
  moveTo(event);
}
function move(event: PointerEvent) { if (dragging) moveTo(event); }
function up() { if (dragging) { dragging = false; render(); } }

async function save(style: Style | null) {
  try {
    const d = props.photo
      ? await post<{ message: string }>("/api/captions/media", { photo: props.photo, style })
      : await post<{ message: string }>(`/api/captions/${props.scope}`, { style });
    notify(d.message);
    emit("saved");
    emit("close");
  } catch (e) {
    notify((e as Error).message, true);
  }
}

function onKey(event: KeyboardEvent) { if (event.key === "Escape") emit("close"); }

onMounted(async () => {
  window.addEventListener("keydown", onKey);
  data.value = await get<CaptionData>(`/api/captions${props.photo ? `?photo=${encodeURIComponent(props.photo)}` : ""}`);
  apply({ ...(media.value ? (data.value.media_style || data.value.styles.photo) : data.value.styles[props.scope]) });
  if (!sample.value) sample.value = data.value.samples[scopeKey.value] || "";
  render();
});
onUnmounted(() => {
  window.removeEventListener("keydown", onKey);
  if (preview.value) URL.revokeObjectURL(preview.value);
});
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div class="dialog" role="dialog" aria-modal="true">
      <header><h2>{{ title }}</h2><button class="btn icon" type="button" :title="t('Fermer')" @click="emit('close')"><i class="fas fa-times"></i></button></header>
      <div v-if="data" class="body">
        <div class="left">
          <div ref="stage" class="stage" :class="{ fixed: scopeKey === 'polaroid' }" @pointerdown="down" @pointermove="move" @pointerup="up">
            <img ref="image" :src="preview" :alt="t('Aperçu de la légende')" draggable="false">
            <span v-if="scopeKey !== 'polaroid'" class="pin" :style="{ left: state.x + '%', top: state.y + '%' }"></span>
            <i v-if="busy" class="fas fa-spinner fa-spin spinner"></i>
          </div>
          <p v-if="scopeKey !== 'polaroid'" class="small muted"><i class="fas fa-hand-pointer"></i> {{ t("Touchez ou faites glisser sur l'image pour placer la légende. L'aperçu est dessiné par le cadre lui-même.") }}</p>
          <label class="label">{{ t("Texte d'essai") }}<input v-model="sample" type="text" maxlength="300" @input="render"></label>
        </div>
        <div class="controls">
          <span class="label">{{ t("Modèles") }}</span>
          <div class="chips"><button v-for="[key, label] in presets" :key="key" type="button" class="chip" @click="apply({ ...state, ...data.presets[key] })">{{ label }}</button></div>
          <span class="label">{{ t("Police") }}</span>
          <div class="chips"><button v-for="[key, label] in fonts" :key="key" type="button" class="chip" :class="['font-' + key, { on: state.font === key }]" @click="set('font', key)">{{ label }}</button></div>
          <label class="label">{{ t("Taille") }} <b>{{ state.size }}%</b>
            <input type="range" min="1.5" max="15" step="0.1" :value="state.size" @input="set('size', Number(($event.target as HTMLInputElement).value))"></label>
          <span class="label">{{ t("Mise en forme") }}</span>
          <div class="chips">
            <button type="button" class="chip" :class="{ on: state.bold }" :title="t('Gras')" @click="set('bold', !state.bold)"><i class="fas fa-bold"></i></button>
            <button type="button" class="chip" :class="{ on: state.italic }" :title="t('Italique')" @click="set('italic', !state.italic)"><i class="fas fa-italic"></i></button>
            <button type="button" class="chip" :class="{ on: state.underline }" :title="t('Souligné')" @click="set('underline', !state.underline)"><i class="fas fa-underline"></i></button>
            <button type="button" class="chip" :class="{ on: state.uppercase }" :title="t('Majuscules')" @click="set('uppercase', !state.uppercase)">AA</button>
            <button v-for="a in ['left', 'center', 'right']" :key="a" type="button" class="chip" :class="{ on: state.align === a }"
                    :title="{ left: t('Aligné à gauche'), center: t('Centré'), right: t('Aligné à droite') }[a]" @click="set('align', a)"><i class="fas" :class="'fa-align-' + a"></i></button>
          </div>
          <span class="label">{{ t("Couleur du texte") }}</span>
          <div class="colors">
            <button v-for="c in SWATCHES" :key="c" type="button" class="swatch" :class="{ on: state.color === c }" :style="{ background: c }" :title="c" @click="set('color', c)"></button>
            <input type="color" :value="state.color" :title="t('Autre couleur')" @input="set('color', ($event.target as HTMLInputElement).value)">
          </div>
          <span class="label">{{ t("Fond") }}</span>
          <div class="chips"><button v-for="[key, label] in backgrounds" :key="key" type="button" class="chip" :class="{ on: state.background === key }" @click="set('background', key)">{{ label }}</button></div>
          <div v-if="state.background !== 'none'" class="sub">
            <div class="colors">
              <button v-for="c in SWATCHES" :key="c" type="button" class="swatch" :class="{ on: state.bg_color === c }" :style="{ background: c }" @click="set('bg_color', c)"></button>
              <input type="color" :value="state.bg_color" @input="set('bg_color', ($event.target as HTMLInputElement).value)">
            </div>
            <label class="label">{{ t("Opacité du fond") }} <b>{{ state.bg_opacity }}%</b>
              <input type="range" min="0" max="100" step="5" :value="state.bg_opacity" @input="set('bg_opacity', Number(($event.target as HTMLInputElement).value))"></label>
          </div>
          <label class="label">{{ t("Contour") }} <b>{{ state.outline || t("aucun") }}</b>
            <input type="range" min="0" max="10" step="1" :value="state.outline" @input="set('outline', Number(($event.target as HTMLInputElement).value))"></label>
          <div v-if="state.outline" class="sub colors">
            <button v-for="c in SWATCHES" :key="c" type="button" class="swatch" :class="{ on: state.outline_color === c }" :style="{ background: c }" @click="set('outline_color', c)"></button>
            <input type="color" :value="state.outline_color" @input="set('outline_color', ($event.target as HTMLInputElement).value)">
          </div>
          <span class="label">{{ t("Effet") }}</span>
          <div class="chips"><button v-for="[key, label] in shadows" :key="key" type="button" class="chip" :class="{ on: state.shadow === key }" @click="set('shadow', key)">{{ label }}</button></div>
          <div v-if="state.shadow !== 'none'" class="sub colors">
            <button v-for="c in SWATCHES" :key="c" type="button" class="swatch" :class="{ on: state.shadow_color === c }" :style="{ background: c }" @click="set('shadow_color', c)"></button>
            <input type="color" :value="state.shadow_color" @input="set('shadow_color', ($event.target as HTMLInputElement).value)">
          </div>
          <label class="label">{{ t("Inclinaison") }} <b>{{ state.rotation }}°</b>
            <input type="range" min="-45" max="45" step="1" :value="state.rotation" @input="set('rotation', Number(($event.target as HTMLInputElement).value))"></label>
          <label class="label">{{ t("Largeur maximale") }} <b>{{ state.width }}%</b>
            <input type="range" min="20" max="100" step="1" :value="state.width" @input="set('width', Number(($event.target as HTMLInputElement).value))"></label>
          <template v-if="scopeKey !== 'polaroid'">
            <span class="label">{{ t("Position") }}</span>
            <div class="chips">
              <button type="button" class="chip" @click="set('y', 8)">{{ t("En haut") }}</button>
              <button type="button" class="chip" @click="set('y', 50)">{{ t("Au milieu") }}</button>
              <button type="button" class="chip" @click="set('y', 92)">{{ t("En bas") }}</button>
            </div>
          </template>
        </div>
      </div>
      <div v-else class="body"><div class="skeleton" style="height: 300px"></div></div>
      <footer>
        <button v-if="!media" class="btn" type="button" @click="apply({ ...data!.defaults[scope] })">{{ t("Style par défaut") }}</button>
        <button v-if="media && data?.media_style" class="btn" type="button" @click="save(null)">{{ t("Reprendre le style général") }}</button>
        <span class="spacer"></span>
        <button class="btn" type="button" @click="emit('close')">{{ t("Annuler") }}</button>
        <button class="btn primary" type="button" @click="save({ ...state })"><i class="fas fa-check"></i>{{ t("Enregistrer") }}</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
@font-face { font-family: "Caveat"; src: url("/static/fonts/Caveat-Regular.ttf"); }
@font-face { font-family: "Patrick Hand"; src: url("/static/fonts/PatrickHand-Regular.ttf"); }
@font-face { font-family: "Permanent Marker"; src: url("/static/fonts/PermanentMarker-Regular.ttf"); }
@font-face { font-family: "Special Elite"; src: url("/static/fonts/SpecialElite-Regular.ttf"); }
.font-caveat { font-family: "Caveat", cursive; font-size: 1.1rem; }
.font-patrick { font-family: "Patrick Hand", cursive; }
.font-marker { font-family: "Permanent Marker", cursive; }
.font-elite { font-family: "Special Elite", monospace; }
.font-serif { font-family: Georgia, serif; }
.backdrop { position: fixed; inset: 0; z-index: 70; background: rgba(10, 12, 20, .55); display: grid; place-items: center; padding: 1rem; }
.dialog { width: min(1100px, 100%); max-height: calc(100vh - 2rem); display: flex; flex-direction: column; background: var(--surface); border-radius: 18px; overflow: hidden; box-shadow: var(--shadow); }
header, footer { display: flex; align-items: center; gap: .6rem; padding: .8rem 1rem; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
header { justify-content: space-between; }
footer { border-top: 1px solid var(--border); border-bottom: 0; }
.body { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 1.2rem; padding: 1rem; overflow: auto; }
.left { display: grid; gap: .6rem; align-content: start; }
.stage { position: relative; border-radius: 12px; overflow: hidden; background: #111; touch-action: none; cursor: crosshair; user-select: none; min-height: 140px; }
.stage.fixed { cursor: default; }
.stage img { display: block; width: 100%; }
.pin { position: absolute; width: 26px; height: 26px; margin: -13px 0 0 -13px; border-radius: 50%; border: 2px dashed #fff; box-shadow: 0 0 0 1px rgba(0, 0, 0, .45); pointer-events: none; }
.spinner { position: absolute; top: 8px; right: 10px; color: #fff; text-shadow: 0 0 4px #000; }
.controls { display: flex; flex-direction: column; gap: .45rem; }
.label { font-size: .82rem; font-weight: 700; color: var(--muted); display: grid; gap: .2rem; margin-top: .3rem; }
.label b { color: var(--text); }
.label input[type="text"] { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; }
.label input[type="range"] { accent-color: var(--accent); }
.chips, .colors { display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; }
.chip { border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: 999px; padding: .3rem .75rem; font: inherit; font-size: .88rem; cursor: pointer; }
.chip.on { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
.swatch { width: 26px; height: 26px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 0 1px var(--border); cursor: pointer; padding: 0; }
.swatch.on { box-shadow: 0 0 0 2px var(--accent); }
.colors input[type="color"] { width: 34px; height: 30px; padding: 0 2px; border-radius: 8px; border: 1px solid var(--border); background: none; }
.sub { padding: .5rem .6rem; border-radius: 10px; background: var(--surface-2); display: grid; gap: .4rem; }
@media (max-width: 800px) {
  .body { grid-template-columns: 1fr; padding-top: 0; }
  .left { position: sticky; top: 0; z-index: 2; background: var(--surface); padding-top: .8rem; }
  .backdrop { padding: 0; }
  .dialog { max-height: 100vh; height: 100%; border-radius: 0; }
}
</style>
