# Nouvelle interface de Pimmich (essai)

Vue 3 + Vite + TypeScript. Elle s'ouvre sur `/app` et utilise les mêmes API JSON que l'interface classique
(`/configure`), qui reste l'interface par défaut. Les rubriques pas encore refaites renvoient vers l'interface classique.

- `npm install` puis `npm run build` : vérifie les types et compile dans `static/app/` (fichiers versionnés : le Raspberry Pi
  n'a pas besoin de Node, un `git pull` suffit) ;
- `npm run dev` : serveur de développement ; lancer en parallèle le bac à sable `python tests/ui/serve_sandbox.py`
  (les appels `/api` lui sont relayés) ;
- textes : écrits en français avec `t("…")` (paramètres `{n}`), traduits par les catalogues du projet (voir
  `procedure_trad.md`) et servis par `/api/i18n`.

Pages refaites : Accueil, Carte des voyages, Statistiques.
