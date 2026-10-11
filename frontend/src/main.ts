import { createApp } from "vue";
import App from "./App.vue";
import { router } from "./router";
import { boot } from "./boot";
import { loadMessages } from "./i18n";
import { applyTheme } from "./theme";
import "./style.css";

applyTheme();
loadMessages(boot.lang).then(() => createApp(App).use(router).mount("#app"));
