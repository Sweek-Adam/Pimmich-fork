import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Compilation dans static/app/ (servi par Flask sous /static/app/) ; en développement, `npm run dev` relaie
// les appels /api vers un Pimmich local (bac à sable des tests sur 127.0.0.1:5055).
export default defineConfig({
  // Chemins absolus (/static/...) laissés tels quels : ce sont des fichiers servis par Flask
  plugins: [vue({ template: { transformAssetUrls: { includeAbsolute: false } } })],
  base: "/static/app/",
  build: {
    outDir: "../static/app",
    emptyOutDir: true,
    assetsDir: "assets",
    chunkSizeWarningLimit: 400,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:5055", "/static": "http://127.0.0.1:5055", "/app": "http://127.0.0.1:5055" },
  },
});
