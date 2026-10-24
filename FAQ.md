# ❓ Foire Aux Questions (FAQ) - Pimmich

Voici une liste de questions fréquemment posées pour vous aider à utiliser et dépanner Pimmich.

> Ce dépôt est un **fork personnel** de [Pimmich](https://github.com/gotenash/pimmich) (usage purement perso). Les chemins
> indiqués ci-dessous (ex : `Écran > Affichage`) sont ceux du menu de la nouvelle interface d'administration.

---

### Questions Générales

**Q : Qu'est-ce que Pimmich ?**

**R :** Pimmich est un logiciel qui transforme un Raspberry Pi en un cadre photo numérique intelligent. Il peut afficher des photos et des vidéos depuis un serveur [Immich](https://immich.app/), Google Drive, Dropbox, OneDrive, un album partagé iCloud, une clé USB, un partage réseau (Samba/Windows), un smartphone, WhatsApp ou même via l'application de messagerie Telegram.

**Q : De quoi ai-je besoin pour utiliser Pimmich ?**

**R :** Il vous faut :
- Un Raspberry Pi (modèle 3B+, 4 ou 5 recommandé) avec son alimentation.
- Une carte SD avec Raspberry Pi OS Trixie (64-bit) installé.
- Un écran.
- Une connexion Internet (Wi-Fi ou Ethernet).

---

### Installation et Configuration

**Q : Comment installer Pimmich ?**

**R :** L'installation est conçue pour être simple :
1. Clonez le dépôt GitHub : `git clone https://github.com/Sweek-Adam/Pimmich-fork.git pimmich`
2. Allez dans le dossier : `cd pimmich`
3. Rendez le script d'installation exécutable : `chmod +x setup.sh`
4. Lancez le script avec les droits d'administrateur : `sudo ./setup.sh`
5. Redémarrez : `sudo reboot`

Le script s'occupe d'installer toutes les dépendances et de configurer le système pour un démarrage automatique.

**Q : Comment accéder à l'interface d'administration ?**

**R :** Une fois le Raspberry Pi démarré, ouvrez un navigateur web sur un autre appareil (ordinateur, smartphone) connecté au même réseau et tapez l'adresse IP de votre Raspberry Pi, par exemple `http://192.168.1.25` : vous êtes redirigé vers `https://`. Le certificat est auto-signé, le navigateur affiche donc un avertissement la première fois. Si vous ne connaissez pas l'IP, elle est affichée sur l'écran du cadre au premier démarrage ou si aucune photo n'est trouvée.

**Q : Il y a deux interfaces : laquelle utiliser ?**

**R :** Après la connexion, c'est la nouvelle interface qui s'ouvre (`/app`) : elle est adaptée au téléphone, a un mode sombre, une recherche et une visite guidée. L'ancienne interface reste accessible par le lien « Interface classique » en bas du menu ; Pimmich se souvient de votre choix. Quelques réglages n'existent encore que dans l'interface classique : un lien y mène directement depuis la page concernée.

**Q : J'ai oublié mon mot de passe pour l'interface web. Comment le réinitialiser ?**

**R :** S'il existe un autre compte administrateur, il peut réinitialiser votre mot de passe dans `Système > Comptes`. Sinon, la méthode la plus simple est de relancer une partie du script d'installation :
1. Connectez-vous en SSH à votre Raspberry Pi.
2. Supprimez l'ancien fichier d'identifiants avec la commande : `sudo rm /boot/firmware/credentials.json`
3. Allez dans le dossier du projet : `cd pimmich`
4. Relancez le script d'installation : `sudo ./setup.sh`

Le script est conçu pour être relancé sans risque. Il détectera l'absence du fichier d'identifiants et en créera un nouveau. Le nouveau mot de passe sera affiché directement dans le terminal à la fin du processus. Pensez à le noter !

**Q : Comment obtenir un Token API Immich ?**

**R :**
1. Connectez-vous à votre interface web Immich.
2. Allez dans "Paramètres du compte" (via votre icône de profil).
3. Dans la section "Clés API", cliquez sur "Générer une nouvelle clé API".
4. Donnez-lui un nom (ex: "Pimmich") et copiez la clé générée.
5. Collez-la dans `Photos > Sources`, carte Immich.

*Conseil :* Pour plus de sécurité, créez un utilisateur Immich dédié pour le cadre avec un accès limité à un seul album partagé.

---

### Fonctionnalités

**Q : Comment fonctionne la fonction Telegram ?**

**R :** Elle vous permet, ainsi qu'à des invités, d'envoyer des photos directement sur le cadre.
1.  **Créez un bot** sur Telegram en parlant à `@BotFather`. Il vous donnera un **Token**.
2.  **Obtenez votre ID utilisateur** Telegram en parlant à un bot comme `@userinfobot`.
3.  Entrez ces deux informations dans `Partage > Telegram`.
4.  Vous pouvez ensuite créer des liens d'invitation sécurisés et temporaires pour vos proches.

**Q : Comment mes proches peuvent-ils envoyer des photos, des messages ou des dessins ?**

**R :** Activez la page invités dans `Partage > Invités`. Depuis le Wi-Fi de la maison, vos proches y envoient des photos, écrivent un message, font un dessin avec des autocollants, enregistrent un message vocal ou réagissent à la photo affichée. Un QR code peut s'afficher sur le cadre pour y accéder. Pour un accès depuis l'extérieur, un lien invité passe par Tailscale (une seule fois : `~/pimmich/utils/enable_remote_guests.sh` sur le Raspberry Pi). Les photos des invités passent par `Partage > À valider`, sauf pour les invités de confiance ; messages et dessins restent ensuite dans le livre d'or.

**Q : À quoi sert la rubrique "Favoris" ?**

**R :** En marquant une photo comme favorite (via l'icône étoile <i class="fas fa-star"></i> dans `Photos > Bibliothèque`), vous augmentez sa fréquence d'apparition dans le diaporama. Vous pouvez régler le "facteur de boost" dans `Écran > Affichage` pour qu'elles apparaissent plus ou moins souvent.

**Q : Qu'est-ce que l'effet "Carte Postale" ?**

**R :** C'est un filtre qui ajoute un cadre blanc et un espace pour une légende (si vous en ajoutez une via l'interface) à vos photos, leur donnant un aspect de carte postale. Les photos envoyées via Telegram utilisent cet effet par défaut pour un rendu plus personnel et chaleureux.

**Q : Peut-on n'afficher que les vidéos ?**

**R :** Oui : sur l'`Accueil`, choisissez « Vidéos seulement ». Le cadre enchaîne alors toutes les vidéos, sans photo ni carte spéciale ; revenez à « Photos et vidéos » pour le diaporama habituel.

**Q : Les GIF animés sont-ils pris en charge ?**

**R :** Oui, par tous les imports : téléphone, invités, Google Drive et autres clouds, Immich, iCloud, Samba, clé USB, e-mail, WhatsApp et Telegram. Telegram envoie les GIF sous forme de petite vidéo : le cadre les reconvertit en GIF. Le GIF s'anime en photo seule (le zoom lent est alors désactivé) comme dans les dispositions, où il garde sa place, son inclinaison et ce qui le recouvre. Les dispositions qui changent les couleurs des photos (photomaton, pellicule, album ancien) gardent le GIF immobile, sur sa première image. Les effets Polaroid et Carte postale aussi.

**Q : Comment afficher l'heure, la météo, les marées ou l'agenda ?**

**R :** Tout se règle dans `Écran > Horloge & météo` : heure et date (police, taille, couleurs, fond), météo (clé OpenWeatherMap), marées (clé StormGlass et coordonnées du port), agenda Google (adresse iCal secrète) et comptes à rebours. L'heure et la météo restent visibles sur les dispositions (mosaïque, mur...).

**Q : Quelles sont les commandes vocales disponibles ?**

**R :** Activez-les dans `Système > Commande vocale`, puis commencez toutes vos commandes par le mot-clé **"Cadre Magique"**. Voici les commandes principales :

*   **Contrôle du Diaporama :**
    *   *"photo suivante"* / *"photo précédente"*
    *   *"pause"* / *"lecture"* (pour mettre en pause ou reprendre)
*   **Gestion de l'Affichage :**
    *   *"règle la durée à 15 secondes"*
    *   *"affiche pendant 30 secondes"*
*   **Gestion des Playlists & Sources :**
    *   *"lance la playlist Vacances"*
    *   *"afficher les cartes postales"* (lance un diaporama des photos Telegram)
    *   *"activer la source Samba"* / *"désactiver la source USB"*
*   **Contrôle du Système :**
    *   *"passer en mode veille"* (éteint l'écran)
    *   *"réveiller le cadre"* (rallume l'écran)
    *   *"éteindre le cadre"* (éteint complètement le Raspberry Pi)
    *   *"revenir au diaporama principal"* (quitte une playlist en cours et relance le diaporama normal)

---

### Dépannage (Troubleshooting)

**Q : J'ai un problème, où puis-je trouver de l'aide ?**

**R :** La rubrique `Système > Journaux` est le meilleur endroit pour commencer : chaque service (serveur web, diaporama, commande vocale...) y a son journal, avec un filtre « Erreurs seulement » et un suivi en direct. `Système > Maintenance` montre aussi l'état du matériel (température, alimentation, carte SD).

**Q : Mon écran ne s'éteint pas complètement, il reste rétro-éclairé. Que faire ?**

**R :** Certains écrans ne répondent pas correctement à la commande de mise en veille logicielle (DPMS). Essayez d'abord HDMI-CEC (`Écran > Affichage`, si votre téléviseur le gère). Sinon, la solution la plus fiable est d'utiliser une prise connectée Wi-Fi pour couper physiquement l'alimentation de l'écran : activez l'option "Prise Connectée" dans l'onglet `Affichage` de l'interface classique et renseignez les URLs pour allumer et éteindre votre prise. De nombreuses prises (Tasmota, Shelly, Kasa, etc.) peuvent être contrôlées par de simples requêtes HTTP.

**Q : Les vidéos ne sont pas fluides ou ne s'affichent pas. Que faire ?**

**R :** Dans `Écran > Affichage`, essayez d'activer l'option "**Activer le décodage vidéo matériel**". C'est beaucoup plus performant, surtout sur Raspberry Pi. Si cela cause des problèmes (écran noir/bleu après une vidéo), désactivez-la.

**Q : Le cadre peut-il retenir plusieurs réseaux Wi-Fi ? Et s'il n'en trouve aucun ?**

**R :** Oui : `Système > Réseau`, carte « Réseaux mémorisés ». Ajoutez autant de réseaux que vous voulez, même s'ils ne sont pas à portée (pratique avant d'emporter le cadre chez quelqu'un), et rangez-les par ordre de préférence. Sans aucun réseau, le cadre démarre quand même et affiche les photos déjà présentes. Si l'heure n'a pas pu être mise à jour, faute d'Internet, il ignore les heures d'affichage pour ne pas rester éteint par erreur. Avec le « Point d'accès de secours » activé, il crée au bout de 2 minutes son propre Wi-Fi « Cadre-Pimmich » : le mot de passe et un QR code s'affichent à l'écran ; connectez-y votre téléphone, ouvrez `http://10.42.0.1`, puis ajoutez le réseau du lieu dans `Système > Réseau`.

**Q : Le Wi-Fi ne se connecte pas, mais l'Ethernet (câble) fonctionne. Pourquoi ?**

**R :** Parfois, si un câble Ethernet est branché, le système lui donne la priorité. Dans `Système > Réseau`, vous pouvez essayer de désactiver temporairement l'"**Interface Filaire (eth0)**" pour forcer le système à utiliser exclusivement le Wi-Fi.

**Q : Comment mettre à jour Pimmich ?**

**R :** Allez dans `Système > Maintenance` et cliquez sur "**Lancer la mise à jour**". Pimmich télécharge la dernière version depuis GitHub puis redémarre ; si la nouvelle version ne démarre pas, il revient tout seul à la précédente. Un bouton permet aussi de revenir manuellement à la version précédente.

**Q : J'ai modifié un réglage mais rien ne change sur le diaporama.**

**R :** Dans la nouvelle interface, les réglages sont enregistrés automatiquement et le diaporama est relancé tout seul quelques secondes après une série de changements (sauf pendant un import, pour ne pas l'interrompre). Si rien ne change, regardez `Système > Journaux` ; en dernier recours, redémarrez le cadre depuis `Système > Maintenance`. Un réglage modifié par erreur peut être annulé depuis l'`Accueil` (« Dernières actions »).

**Q : Comment protéger la carte SD et sauvegarder le cadre ?**

**R :** `Système > Maintenance` permet de faire une sauvegarde complète restaurable (réglages, comptes, messages...) et indique si la protection contre l'usure est active. Pour l'activer, lancez une fois sur le Raspberry Pi `sudo ~/pimmich/utils/enable_sd_protection.sh` puis redémarrez : les journaux sont alors écrits en mémoire vive (log2ram). Ajoutez `--zram` pour placer aussi la mémoire d'échange en mémoire compressée.

**Q : J'ai flashé l'image sur une carte SD plus grande : comment utiliser tout l'espace ?**

**R :** `Système > Maintenance`, carte « Système de Fichiers de la Carte SD » : elle indique la taille de la partition et de la carte. S'il reste de la place inutilisée, le bouton « Étendre le système de fichiers » prépare l'agrandissement, qui se termine au prochain redémarrage (aucune donnée n'est supprimée).
