<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { get, post } from "../api";
import { t } from "../i18n";
import { run } from "../toast";

interface User { username: string; role: string; created: string }
interface Accounts { me: string; admin: boolean; main_admin: string; users: User[] }

const data = ref<Accounts | null>(null);
const mine = reactive({ new_password: "", confirm_password: "" });
const create = reactive({ username: "", password: "", role: "user" });

async function load() {
  data.value = await get<Accounts>("/api/accounts");
}

async function changeMine() {
  const done = await run(() => post("/api/accounts/password", mine));
  if (done) Object.assign(mine, { new_password: "", confirm_password: "" });
}

async function addUser() {
  const done = await run(() => post("/api/accounts", create));
  if (done) { Object.assign(create, { username: "", password: "", role: "user" }); load(); }
}

async function setRole(user: User, role: string) {
  await run(() => post(`/api/accounts/${encodeURIComponent(user.username)}/role`, { role }));
  load();
}

async function resetPassword(user: User) {
  const password = window.prompt(t("Nouveau mot de passe pour « {name} » :", { name: user.username }));
  if (!password) return;
  await run(() => post(`/api/accounts/${encodeURIComponent(user.username)}/password`, { password }));
}

async function remove(user: User) {
  if (!window.confirm(t("Supprimer le compte « {name} » ?", { name: user.username }))) return;
  await run(() => post(`/api/accounts/${encodeURIComponent(user.username)}`, {}, "DELETE"));
  load();
}

onMounted(load);
</script>

<template>
  <div v-if="!data" class="card"><div class="skeleton" style="height: 200px"></div></div>
  <template v-else>
    <section class="card">
      <div class="card-head"><h2><i class="fas fa-key"></i>{{ t("Mon compte") }} · {{ data.me }}</h2></div>
      <form class="fields" autocomplete="off" @submit.prevent="changeMine">
        <label>{{ t("Nouveau mot de passe") }}<input v-model="mine.new_password" type="password" autocomplete="new-password" minlength="6" required></label>
        <label>{{ t("Confirmer le mot de passe") }}<input v-model="mine.confirm_password" type="password" autocomplete="new-password" minlength="6" required></label>
        <div><button class="btn primary" type="submit"><i class="fas fa-check"></i>{{ t("Changer le mot de passe") }}</button></div>
      </form>
    </section>

    <template v-if="data.admin">
      <section class="card">
        <div class="card-head"><h2><i class="fas fa-users"></i>{{ t("Comptes de la famille") }}</h2></div>
        <p class="small muted">{{ t("Administrateur principal : {name}", { name: data.main_admin }) }}</p>
        <p v-if="!data.users.length" class="muted">{{ t("Aucun autre compte pour l'instant.") }}</p>
        <ul class="users">
          <li v-for="user in data.users" :key="user.username">
            <span class="spacer"><strong>{{ user.username }}</strong>
              <span v-if="user.created" class="small muted"> · {{ t("créé le") }} {{ user.created }}</span></span>
            <span v-if="user.username === data.me" class="pill off">{{ user.role === "admin" ? t("Administrateur") : t("Utilisateur") }}</span>
            <select v-else :value="user.role" @change="setRole(user, ($event.target as HTMLSelectElement).value)">
              <option value="user">{{ t("Utilisateur") }}</option>
              <option value="admin">{{ t("Administrateur") }}</option>
            </select>
            <button class="btn icon" type="button" :title="t('Changer le mot de passe')" @click="resetPassword(user)"><i class="fas fa-key"></i></button>
            <button v-if="user.username !== data.me" class="btn icon danger" type="button" :title="t('Supprimer')" @click="remove(user)"><i class="fas fa-trash-alt"></i></button>
          </li>
        </ul>
      </section>

      <section class="card">
        <div class="card-head"><h2><i class="fas fa-user-plus"></i>{{ t("Ajouter un compte") }}</h2></div>
        <form class="fields grid-form" autocomplete="off" @submit.prevent="addUser">
          <label>{{ t("Nom d'utilisateur") }}<input v-model="create.username" type="text" autocomplete="off" required></label>
          <label>{{ t("Mot de passe") }}<input v-model="create.password" type="password" autocomplete="new-password" minlength="6" required></label>
          <label>{{ t("Rôle") }}
            <select v-model="create.role"><option value="user">{{ t("Utilisateur") }}</option><option value="admin">{{ t("Administrateur") }}</option></select></label>
          <div class="submit"><button class="btn primary" type="submit"><i class="fas fa-plus"></i>{{ t("Créer le compte") }}</button></div>
        </form>
        <p class="small muted">{{ t("Chaque compte a ses propres envois et ses playlists ; un utilisateur ne voit pas les réglages sensibles.") }}</p>
      </section>
    </template>
  </template>
</template>

<style scoped>
.fields { display: grid; gap: .7rem; max-width: 520px; }
.fields label { display: grid; gap: .25rem; font-weight: 600; font-size: .9rem; }
.fields input, .fields select, .users select { font: inherit; font-weight: 400; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: .45rem .7rem; }
.grid-form { max-width: none; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); align-items: end; margin-bottom: .7rem; }
.users { list-style: none; padding: 0; margin: .5rem 0 0; }
.users li { display: flex; align-items: center; gap: .5rem; padding: .5rem 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.users .btn.icon { width: 2.2rem; height: 2.2rem; }
</style>
