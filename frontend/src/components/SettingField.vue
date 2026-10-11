<script setup lang="ts">
import { computed, ref } from "vue";
import { t } from "../i18n";
import { saveSecret, secrets, setValue, values, type Field } from "../settings";


const props = defineProps<{ field: Field }>();
const value = computed(() => values[props.field.key]);
const visible = computed(() => !props.field.showIf || props.field.showIf(values));
const id = computed(() => `setting-${props.field.key}`);
const secret = ref("");

async function storeSecret(value: string) {
  if (await saveSecret(props.field.key, value)) secret.value = "";
}

function update(raw: string | boolean) {
  const f = props.field;
  if (f.type === "toggle") return setValue(f.key, raw as boolean);
  if (f.type === "number" || f.type === "range") {
    const number = Number(raw);
    if (raw === "" || Number.isNaN(number)) return;
    return setValue(f.key, number);
  }
  setValue(f.key, raw as string);
}
</script>

<template>
  <div v-if="visible" class="field" :class="field.type">
    <template v-if="field.type === 'toggle'">
      <label class="toggle-row" :for="id">
        <span class="text"><span>{{ field.label() }}</span><small v-if="field.help" class="muted">{{ field.help() }}</small></span>
        <input :id="id" type="checkbox" class="switch" :checked="!!value" @change="update(($event.target as HTMLInputElement).checked)">
      </label>
    </template>
    <template v-else>
      <label :for="id" class="label">{{ field.label() }}</label>
      <div class="control">
        <select v-if="field.type === 'select'" :id="id" :value="value" @change="update(($event.target as HTMLSelectElement).value)">
          <option v-for="o in field.options!()" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <template v-else-if="field.type === 'range'">
          <input :id="id" type="range" :min="field.min" :max="field.max" :step="field.step || 1" :value="value"
                 @change="update(($event.target as HTMLInputElement).value)" @input="values[field.key] = Number(($event.target as HTMLInputElement).value)">
          <output>{{ value }}{{ field.unit || "" }}</output>
        </template>
        <template v-else-if="field.type === 'timeOrSunset'">
          <select :id="id" :value="value === 'sunset' ? 'sunset' : 'time'" @change="update(($event.target as HTMLSelectElement).value === 'sunset' ? 'sunset' : '21:00')">
            <option v-for="o in field.options!()" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
          <input v-if="value !== 'sunset'" type="time" :value="value" @change="update(($event.target as HTMLInputElement).value)">
        </template>
        <input v-else-if="field.type === 'time'" :id="id" type="time" :value="value" @change="update(($event.target as HTMLInputElement).value)">
        <template v-else-if="field.type === 'color'">
          <input type="color" :value="String(value || '#000000').slice(0, 7)" :aria-label="field.label()"
                 @change="update(($event.target as HTMLInputElement).value + String(value || '').slice(7))">
          <input :id="id" type="text" class="hex" :value="value" maxlength="9" @change="update(($event.target as HTMLInputElement).value.trim())">
        </template>
        <template v-else-if="field.type === 'secret'">
          <input :id="id" v-model="secret" type="password" class="text-input" autocomplete="off"
                 :placeholder="secrets[field.key] ? t('Enregistré (laisser vide pour garder)') : t('Non défini')">
          <button class="btn small" type="button" :disabled="!secret.trim()" @click="storeSecret(secret)">{{ t("Enregistrer") }}</button>
          <button v-if="secrets[field.key]" class="btn small danger" type="button" @click="storeSecret('')">{{ t("Effacer") }}</button>
          <span v-if="secrets[field.key]" class="pill ok"><i class="fas fa-lock"></i></span>
        </template>
        <input v-else-if="field.type === 'text'" :id="id" type="text" class="text-input" :value="value" :placeholder="field.placeholder"
               @change="update(($event.target as HTMLInputElement).value)">
        <template v-else>
          <input :id="id" type="number" :min="field.min" :max="field.max" :step="field.step || 1" :value="value"
                 @change="update(($event.target as HTMLInputElement).value)">
          <span v-if="field.unit" class="muted">{{ field.unit }}</span>
        </template>
      </div>
      <small v-if="field.help" class="muted help">{{ field.help() }}</small>
    </template>
  </div>
</template>

<style scoped>
.field { padding: .7rem 0; border-bottom: 1px solid var(--border); }
.field:last-child { border-bottom: 0; }
.toggle-row { display: flex; align-items: center; gap: 1rem; cursor: pointer; }
.text { flex: 1; display: grid; gap: .15rem; }
.label { display: block; font-weight: 600; margin-bottom: .35rem; }
.control { display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.control input[type="number"], .control input[type="time"], .control select {
  font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem;
}
.control input[type="number"] { width: 7rem; }
.control input[type="text"], .control input[type="password"] { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .4rem .6rem; }
.btn.small { padding: .3rem .8rem; font-size: .85rem; }
.control .hex { width: 8rem; font-family: ui-monospace, monospace; }
.control .text-input { flex: 1; max-width: 360px; }
.control input[type="color"] { width: 2.6rem; height: 2.2rem; padding: 0; border: 1px solid var(--border); border-radius: 8px; background: none; cursor: pointer; }
.control select { max-width: 100%; }
.control input[type="range"] { flex: 1; max-width: 360px; accent-color: var(--accent); }
output { min-width: 3.5rem; font-weight: 600; }
.help { display: block; margin-top: .3rem; }
.switch { appearance: none; width: 2.7rem; height: 1.55rem; border-radius: 999px; background: var(--border); position: relative; cursor: pointer; flex: none; transition: background .15s; }
.switch::after { content: ""; position: absolute; top: .18rem; left: .18rem; width: 1.2rem; height: 1.2rem; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0, 0, 0, .3); transition: transform .15s; }
.switch:checked { background: var(--accent); }
.switch:checked::after { transform: translateX(1.15rem); }
</style>
