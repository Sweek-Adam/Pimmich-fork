# Interface d'administration de Pimmich

> Fait partie de ce **fork personnel** de [Pimmich](https://github.com/gotenash/pimmich) : cette interface a été
> entièrement refaite dans le fork, pour un usage purement perso.

Vue 3 + Vite + TypeScript. Elle s'ouvre sur `/app` et c'est l'interface par défaut après la connexion ; elle utilise
les API JSON du serveur Flask. L'ancienne interface (`/configure?ui=classic`) reste disponible, et le choix est mémorisé.

- `npm install` puis `npm run build` : vérifie les types et compile dans `static/app/` (fichiers versionnés : le Raspberry Pi
  n'a pas besoin de Node, un `git pull` suffit ; l'intégration continue vérifie que la compilation est à jour) ;
- `npm run dev` : serveur de développement ; lancer en parallèle le bac à sable `python tests/ui/serve_sandbox.py`
  (les appels `/api` lui sont relayés) ;
- textes : écrits en français avec `t("…")` (paramètres `{n}`), traduits par les catalogues du projet (voir
  `procedure_trad.md`) et servis par `/api/i18n`.

Toutes les pages de l'administration sont refaites ; quelques réglages ne sont encore que dans l'interface classique (un lien y mène depuis la page concernée).
