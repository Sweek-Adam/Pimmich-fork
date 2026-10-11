<script setup lang="ts">
import { onMounted } from "vue";
import { classicUrl } from "../boot";
import { t } from "../i18n";
import { loadSettings, loaded, type Section } from "../settings";
import { notify } from "../toast";
import SettingField from "./SettingField.vue";

defineProps<{ sections: Section[]; classicTab: string; classicHint?: () => string }>();

onMounted(() => loadSettings().catch((e) => notify((e as Error).message, true)));
</script>

<template>
  <div v-if="!loaded" class="card"><div class="skeleton" style="height: 320px"></div></div>
  <template v-else>
    <p class="small muted autosave"><i class="fas fa-check-circle"></i> {{ t("Les changements sont enregistrés automatiquement.") }}</p>
    <div class="sections">
      <section v-for="section in sections" :key="section.title()" class="card">
        <div class="card-head"><h2><i class="fas" :class="section.icon"></i>{{ section.title() }}</h2></div>
        <p v-if="section.intro" class="small muted">{{ section.intro() }}</p>
        <SettingField v-for="field in section.fields" :key="field.key" :field="field" />
      </section>
    </div>
    <p class="small muted classic">
      <a :href="classicUrl(classicTab)"><i class="fas fa-external-link-alt"></i> {{ classicHint ? classicHint() : t("Autres réglages : interface classique") }}</a>
    </p>
  </template>
</template>

<style scoped>
.autosave { margin-bottom: .8rem; }
.autosave i { color: var(--ok); }
.sections { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr)); gap: 1rem; align-items: start; }
.sections .card + .card { margin-top: 0; }
.classic { margin-top: 1rem; }
</style>
