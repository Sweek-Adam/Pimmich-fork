# 🖼️ Pimmich – Cadre photo connecté intelligent

[![Tests](https://github.com/Sweek-Adam/Pimmich-fork/actions/workflows/tests.yml/badge.svg)](https://github.com/Sweek-Adam/Pimmich-fork/actions/workflows/tests.yml)

Pimmich est une application Python conçue pour transformer un Raspberry Pi en un cadre photo numérique intelligent et personnalisable. Il peut afficher des photos depuis de multiples sources, être contrôlé à la voix, et bien plus encore.

> [!NOTE]
> **Ce dépôt est un fork personnel** de [Pimmich](https://github.com/gotenash/pimmich), le projet d'origine créé par Gadgetaulab.
> Je l'ai repris pour mon propre cadre photo et j'y ai ajouté **plein de fonctionnalités** (liste ci-dessous).
> C'est un **usage purement personnel** : le fork évolue de son côté, n'est plus fusionné avec le dépôt d'origine
> et n'est pas maintenu pour d'autres installations. Pour la version officielle, rendez-vous sur le dépôt d'origine 🙂

<img src="static/pimmich_logo.png" alt="Pimmich Logo" width="300" style="display: block; margin: auto;">

---

## 📖 Table des matières

- [🍴 Ajouts de ce fork](#-ajouts-de-ce-fork)
- [✨ Fonctionnalités Principales](#-fonctionnalités-principales)
- [🧰 Technologies utilisées](#-technologies-utilisées)
- [🚀 Installation](#-installation)
- [🔧 Configuration](#-configuration)
- [🗣️ Contrôle Vocal](#️-contrôle-vocal)
- [❓ Dépannage (FAQ)](#-dépannage-faq)
- [🔑 Récupérer le token Immich](#-récupérer-le-token-immich)
- [🕰️ Historique du projet d'origine](#️-historique-du-projet-dorigine)
- [📜 Licences](#-licences)
- [💖 Crédits](#-crédits)

---

## 🍴 Ajouts de ce fork

En plus de tout ce que propose Pimmich d'origine, ce fork ajoute notamment :

#### 🖥️ Nouvelle interface d'administration
- Interface entièrement refaite (Vue 3), adaptée au téléphone, **mode sombre**, recherche, raccourcis vers chaque rubrique, visite guidée.
- Historique des réglages avec annulation, glisser-déposer sur l'accueil, statistiques, bibliothèque avec recherche (date, source, personne).
- Comptes par membre de la famille (envois et playlists personnels), administration de plusieurs cadres.

#### 📸 Photos & sources
- Google Drive, Dropbox, OneDrive (rclone), albums partagés iCloud, import WhatsApp, partage direct depuis Android.
- Tri automatique (photos floues, sombres, doublons, captures d'écran), personnes reconnues via Immich, recadrage qui garde les visages.
- Albums intelligents, « Ce jour-là », légendes de lieu automatiques, légendes façon Snapchat sur photos et vidéos.
- Plusieurs emplacements de stockage (disque USB, NAS) et rotation automatique de l'écran.
- **Carte du monde des voyages** : regroupement des photos par lieu et par période, récits de voyage affichés sur le cadre.

#### 🖼️ Affichage
- Dispositions (mosaïque, mur, magazine…) préparées à l'avance, mises en page familiales (anniversaires avec prénom et âge, fêtes…).
- Mode **vidéos uniquement**, enchaînement sans écran de chargement.
- Horloge entièrement personnalisable (police, taille, couleurs, fond), météo animée, soleil et lune, citation du jour.
- Agenda familial (Google Agenda), comptes à rebours, fréquences d'affichage réglables, baisse de luminosité le soir et horloge de nuit.
- Nouvelles transitions, synchronisées sur le rythme de la musique, et ambiances saisonnières (Halloween, Noël, Pâques…).

#### 💌 Messages & invités
- Messages programmés ou récurrents, **dessins** avec autocollants, **messages vocaux**, réactions et **livre d'or**.
- Lien invité accessible depuis l'extérieur (Tailscale) et invités de confiance validés automatiquement.

#### 🎵 Musique
- Spotify (lecteur, juke-box avec grande pochette, **karaoké** avec paroles synchronisées), radios internet et podcasts.
- Bluetooth, AirPlay, minuterie de sommeil, musique selon l'heure, volume baissé pendant les vidéos et les messages vocaux.

#### 🏠 Maison connectée & fiabilité
- Home Assistant (MQTT), HDMI-CEC, détection de présence par Wi-Fi, notifications (ntfy).
- Mise à jour en un clic avec retour arrière, surveillance qui relance le diaporama s'il se fige, rotation des journaux.
- Protection de la carte SD (log2ram, zram), sauvegarde complète restaurable, accès HTTPS via Tailscale.
- Tests automatisés et intégration continue.

---

## ✨ Fonctionnalités Principales

Pimmich est riche en fonctionnalités pour offrir une expérience complète et personnalisable :

#### 🖼️ **Affichage & Diaporama**
- **Multi-sources :** Affichez des photos depuis [Immich](https://immich.app/), un partage réseau (Samba/Windows), une clé USB, un smartphone ou via Telegram.
- **Personnalisation avancée :** Réglez la durée d'affichage, les heures d'activité, les transitions (fondu, glissement), et activez un effet de mouvement "Pan & Zoom".
- **Filtres créatifs :** Appliquez des filtres à vos photos (Noir & Blanc, Sépia, Vintage) et des effets uniques comme le **Polaroid** ou la **Carte Postale**.
- **Gestion des formats :** Prise en charge intelligente des photos portraits (fond flou) et des vidéos (avec son et accélération matérielle optionnelle).

#### ⚙️ **Interface & Contrôle**
- **Interface Web complète :** Une interface d'administration locale, protégée par mot de passe, avec un menu par rubriques (Accueil, Photos, Écran, Partage, Système), utilisable aussi sur téléphone.
- **Contrôle Vocal :** Pilotez votre cadre avec des commandes vocales comme *"Cadre Magique, photo suivante"* ou *"Cadre Magique, lance la playlist Vacances"*.
- **Gestion de contenu :**
    - **Playlists :** Créez des albums virtuels, réorganisez les photos par glisser-déposer et lancez des diaporamas thématiques avec un écran de titre dynamique (pêle-mêle de photos sur fond en liège).
    - **Favoris :** Marquez vos photos préférées pour qu'elles apparaissent plus souvent.
    - **Légendes :** Ajoutez du texte personnalisé sur vos photos et cartes postales.

#### 🌐 **Connectivité & Interactions**
- **Telegram :** Permettez à vos proches d'envoyer des photos sur le cadre via un bot Telegram, avec un système d'invitations sécurisé et temporaire.
- **Wi-Fi & Réseau :** Configurez le Wi-Fi, scannez les réseaux et gérez les interfaces réseau directement depuis l'interface.
- **Envoi depuis Smartphone :** Importez des photos directement depuis le navigateur de votre téléphone.

#### 🛠️ **Maintenance & Monitoring**
- **Mise à jour facile :** Mettez à jour Pimmich en un clic depuis l'interface.
- **Sauvegarde & Restauration :** Sauvegardez et restaurez l'ensemble de votre configuration.
- **Monitoring système :** Suivez en temps réel la température, l'utilisation du CPU, de la RAM et du disque avec des graphiques d'historique.
- **Logs détaillés :** Accédez aux journaux de chaque service (serveur web, diaporama, contrôle vocal) pour un dépannage facile.

---

## 🧰 Technologies utilisées

- **Backend :** Python, Flask
- **Interface d'administration :** Vue 3, Vite, TypeScript (compilée dans `static/app/` : le Raspberry Pi n'a pas besoin de Node) ; l'ancienne interface (Jinja, TailwindCSS) reste disponible
- **Diaporama :** Pygame (pygame-ce)
- **Vidéos, musique et messages vocaux :** mpv, PipeWire
- **Traitement d'image :** Pillow, NumPy, OpenCV (détection de visages YuNet)
- **Synchronisation cloud :** rclone (Google Drive, Dropbox, OneDrive)
- **Accès à distance :** Tailscale (lien invité, HTTPS)
- **Contrôle Vocal :** Picovoice Porcupine (mot-clé) & Vosk (reconnaissance)
- **Serveur Web :** NGINX (en tant que reverse proxy, HTTPS)
- **Tests :** pytest, Playwright, intégration continue GitHub Actions

---

## 🚀 Installation

### Installation depuis le dépôt Git

#### ✅ Pré-requis

- Un Raspberry Pi (modèle 3B+, 4 ou 5 recommandé) avec **Raspberry Pi OS Trixie (Debian 13)** Desktop (64-bit) — **Version recommandée**.
- Une carte SD, une alimentation, un écran.
- Une connexion Internet.

#### 📝 Étapes d'installation

1.  **Clonez le dépôt**
    Ouvrez un terminal sur votre Raspberry Pi et exécutez :
    ```bash
    git clone https://github.com/Sweek-Adam/Pimmich-fork.git pimmich
    cd pimmich
    ```

2.  **Lancez le script d'installation**
    Ce script installe toutes les dépendances, configure l'environnement et prépare le démarrage automatique.
    ```bash
    chmod +x setup.sh
    sudo ./setup.sh
    ```

3.  **Redémarrez**
    Une fois le script terminé, un redémarrage est nécessaire pour que tous les services se lancent correctement.
    ```bash
    sudo reboot
    ```

---

## 🔧 Configuration

### 1. Première Connexion

- Au redémarrage, le cadre affichera un QR Code et l'adresse IP du Raspberry Pi.
- Scannez le QR Code ou ouvrez un navigateur sur un autre appareil (PC, smartphone) sur le même réseau et entrez l'adresse IP (ex: `http://192.168.1.XX`) : vous êtes redirigé vers `https://`. Le certificat est auto-signé, le navigateur affiche donc un avertissement la première fois (pour une adresse sans avertissement, voir `Système > Maintenance > HTTPS sans avertissement (Tailscale)`).
- Le mot de passe initial est généré aléatoirement lors de l'installation et est stocké dans le fichier `/boot/firmware/credentials.json`. Il est fortement recommandé de le changer via l'interface (`Système > Comptes`).
- Après la connexion, la nouvelle interface s'ouvre (`/app`). L'ancienne reste accessible depuis le menu (« Interface classique ») et le choix est mémorisé.

### 2. Configuration des Sources

Tout se passe dans `Photos > Sources` :
- **Immich :** Pour connecter votre serveur Immich, vous aurez besoin de :
    1.  **L'URL de votre serveur** (ex: `http://192.168.1.YY:2283`).
    2.  **Un Token API** (voir [Récupérer le token Immich](#-récupérer-le-token-immich)).
    3.  **Le nom de l'album** que vous souhaitez afficher.
- **Google Drive, Dropbox, OneDrive, iCloud :** Suivez l'assistant de chaque carte.
- **Samba / Partage Windows :** Renseignez les informations de votre partage réseau.
- **USB, smartphone, WhatsApp :** Utilisez `Photos > Importer`.

### 3. Personnalisation

Explorez les rubriques du menu pour personnaliser votre cadre :
- **Écran > Affichage :** Réglez les durées, les heures d'activité, les transitions, les effets, le mode vidéos uniquement...
- **Écran > Horloge & météo :** Activez et configurez l'heure, la date, la météo, les marées, l'agenda et les comptes à rebours.
- **Écran > Dispositions :** Choisissez les mises en page (mosaïque, mur, magazine...) et leur fréquence.
- **Photos > Sources :** Cochez les sources que vous souhaitez voir dans le diaporama.
- **Partage > Invités :** Ouvrez la page invités (photos, messages, dessins, messages vocaux, livre d'or).

---

## 🗣️ Contrôle Vocal

Pimmich supporte le contrôle vocal en **Français** et en **Anglais**.

Pour utiliser un mot-clé personnalisé ("Cadre Magique", "Magic Frame"...), une étape manuelle est requise :
1.  Créez un compte gratuit sur la Picovoice Console.
2.  Allez dans la section "Porcupine" et créez votre mot-clé personnalisé.
3.  Téléchargez le modèle pour la plateforme **Raspberry Pi**.
4.  Renommez le fichier `.ppn` téléchargé en `cadre-magique_raspberry-pi.ppn` (pour le français) ou `magic-frame_raspberry-pi_en.ppn` (pour l'anglais, exemple).
5.  Placez ce fichier dans le dossier `voice_models` à la racine du projet Pimmich.
6.  Dans l'interface Pimmich, allez dans `Système > Commande vocale`, sélectionnez la langue, entrez votre "Access Key" Picovoice et activez le service.

### Commandes Disponibles

Une fois le contrôle vocal activé, commencez toutes vos commandes par le mot-clé **"Cadre Magique"**.

**Contrôle du Diaporama :**
- *"photo suivante"*
- *"photo précédente"*
- *"pause"* / *"lecture"* (pour mettre en pause ou reprendre)

**Gestion de l'Affichage :**
- *"règle la durée à 15 secondes"*
- *"affiche pendant 30 secondes"*

**Gestion des Playlists & Sources :**
- *"lance la playlist Vacances"*
- *"afficher les cartes postales"* (lance un diaporama des photos Telegram)
- *"activer la source Samba"*
- *"désactiver la source USB"*

**Contrôle du Système :**
- *"passer en mode veille"* (éteint l'écran)
- *"réveiller le cadre"* (rallume l'écran)
- *"éteindre le cadre"* (éteint complètement le Raspberry Pi)
- *"revenir au diaporama principal"* (quitte une playlist et relance le diaporama normal)

---

## ❓ Dépannage (FAQ)

Pour toute question ou problème, consultez notre **Foire Aux Questions (FAQ.md)**. Vous y trouverez des solutions aux problèmes courants (Wi-Fi, affichage, etc.) et des astuces pour utiliser Pimmich au mieux.

---

## 🕰️ Historique du projet d'origine

Les versions ci-dessous sont celles du projet [Pimmich](https://github.com/gotenash/pimmich) d'origine (Gadgetaulab), avant ce fork. Les ajouts du fork sont décrits dans [🍴 Ajouts de ce fork](#-ajouts-de-ce-fork).

> 🗓️ À partir de juin 2025 — Une version majeure chaque mois

### ✅ Août 2026 - Mises à jour de Stabilité, Performance & Compatibilité Pi 2/3/4/5
- 🚀 **Mise à jour asynchrone & Keep-Alives (anti-timeout) :** Toutes les tâches lourdes (Samba, Immich, photo/video prep) s'exécutent en arrière-plan avec pings réseau toutes les 10s pour éviter toute déconnexion de l'interface d'administration.
- 🔁 **Synchronisation intelligente incrémentale :** Seuls les nouveaux médias et les suppressions sont synchronisés, préservant la bande passante, le CPU et l'usure de la carte SD.
- ⚡ **Optimisation de la mémoire GPU (CMA) :** Technique innovante de réduction de fenêtre 1x1 masquée (`pygame.HIDDEN`) pour libérer 100% de la mémoire GPU lors de la lecture vidéo `mpv`, résolvant les crashs et lenteurs sous Wayland/Sway.
- ⏱️ **Lecture vidéo instantanée :** Suppression des appels lents à `ffprobe` au profit d'un Watchdog de sécurité fixe de 90 secondes. La vidéo se lance en moins d'une seconde.
- 📺 **Affichage vidéo robuste devant le diaporama :** Option `--ontop` sélective pour garantir que les vidéos se lisent toujours au premier plan, devant la fenêtre de Pygame sur Pi 1 et 2.
- 🎨 **Transitions optimisées à 30/60 FPS :** Le fondu enchaîné est calculé à 50% de résolution sur Pi 1/2/3 (75% de pixels en moins à traiter) puis mis à l'échelle via l'accélération matérielle de SDL2, avec un sélecteur de FPS dans l'interface admin.
- 🤫 **Zéro bruit CPU sonore au repos :** Le mixeur audio Pygame n'est initialisé qu'à la demande. Évite de charger les serveurs son (Pipewire) en tâche de fond et économise 40% de CPU sur les anciens Pi.
- 🌐 **Vitesse réseau améliorée :** Optimisation de la détection Wi-Fi pour contourner les appels réseau lents sur les systèmes uniquement câblés (Pi 2).
- 📦 **Dépendances optionnelles :** Support HEIF/HEIC et commandes vocales optionnels pour garantir le succès de l'installation sur toutes les architectures système, géré à la volée dans `setup.sh`.
- 🇫🇷 **Langue française native :** Configuration et génération automatique de la locale `fr_FR.UTF-8` lors de l'installation pour des dates affichées en français natif.

### ✅ Mai 2026 – Version Anniversaire (27 mai)
- 🚀 **Mise à jour fiabilisée :** Le moteur de mise à jour via l'interface est désormais 100% opérationnel et sécurisé.
- 📅 **Boost Anniversaire :** Revivez vos souvenirs avec une priorité d'affichage pour les photos prises à la même date les années passées.
- 🌍 **Métadonnées & Drapeaux :** Affichage personnalisable du lieu, de la date et du drapeau du pays d'origine.
- 📊 **Monitoring Avancé :** Nouveaux graphiques temps réel pour surveiller la santé de votre Raspberry Pi.
- 🔌 **Domotique :** Support des prises connectées pour une extinction totale de l'écran.
- 🖱️ **Playlists UX :** Organisation des albums par glisser-déposer.
- ⚡ **Hardware Accel :** Lecture vidéo optimisée pour Pi 4 et Pi 5.
- 🔘 **Bouton Physique :** Support GPIO pour le contrôle matériel de la veille.
- 🚀 **Compatibilité Debian Trixie (Debian 13) :**
    - ✅ Migration complète vers **Python 3.13**.
    - ✅ Optimisation du rendu vidéo pour **Sway/Wayland** (DMABUF et V4L2-copy).
    - ✅ Support natif du Raspberry Pi 3 sur les nouveaux noyaux Linux.
    - ✅ Sécurisation non-interactive des commandes `sudo` via règles ciblées.

### ✅ Septembre 2025
- 🎨 **Refonte de l'Interface :** Nouvelle navigation par groupes et onglets pour une expérience plus claire et intuitive.
- 🎵 **Gestion de Playlists Améliorée :**
    - ✅ Nouvel écran de lancement dynamique avec un pêle-mêle de photos sur un fond en liège.
    - ✅ Créez des albums virtuels, visualisez leur contenu, renommez-les et lancez des diaporamas thématiques.
- 🔘 **Bouton Physique :**
    - ✅ Ajout du support pour un bouton physique (via GPIO) pour mettre en veille et réveiller le cadre.
- 🗣️ **Contrôle Vocal :**
    - ✅ Ajout de la commande vocale ("Cadre Magique") et intégration profonde avec le système.
- 🚀 **Optimisations et Stabilité :**
    - ✅ Amélioration de la réactivité de l'onglet "Système" grâce à une lecture optimisée des logs.
    - ✅ Fiabilisation du script de mise à jour pour éviter les blocages.
    - ✅ Nombreuses corrections de bugs pour une meilleure stabilité générale.

### ✅ Août 2025
- ✅ Gestion des vidéos
-  Ajout d'une vignette lors de lecture de la vidéo (onglet Actions)
- ✅ Ajout de la fonction "Carte Postle" par telegram
    - ✅ sécurisation par lien d'invitation
- ✅ Gestion accélération matérielle pour Pi3
- ✅ Ajout traduction de l'application (Anglais et Espagnol)
- ✅ Ajout QR Code première connexion
- ✅ Ajout de l'effet "Carte postale" pour toutes les sources de photos
- ✅ Ajout de la fonctionnalité "Ajout de texte"
- ✅ Ajout d'un bouton "Redémarrer l'appli Web"
- ✅ Ajout de l'onglet Favoris (augmentation fréquence d'affichage d'une photo)
- ✅ Modification météo et marées pour afficher 3 jours de prévisions
- ✅ Corrections des bugs
    - ✅ Heure début d'affichage
    - ✅ Effacement des logs dans l'onglet système sans problème de container

### ✅ Juillet 2025

- ✅ 🧭 Ajout de la configuration Wi-Fi depuis l’interface Web  
- ✅ 🗂️ Réorganisation de la page de configuration en onglets  
- ✅ 🔁 Mise à jour automatique périodique de l’album Immich  
- ✅ 📁 Support du protocole SMB pour accéder à des photos partagées en réseau
- ✅ ⏰🌤️ Affichage de l’heure et de la météo sur l’écran
- ✅ Ajout NGINX, plus besoin de mettre le numéro du port (50000)
- ✅ Ajout des filtres (NB, Sépia, Polaroid ...)
- ✅ Ajout des différents boutons supprimer
- ✅ Ajout d'une option de sauvegarde de la configuration
- ✅ Ajout d'un menu changement du mot de passe
- ✅ Ajout de la création du credenrials.json pendant le setup
- ✅ Ajout effet de transition
- ✅ Ajout détection automatique de la résolution
- ✅ Ajout de l'import à partir d'un smartphone (en admin et mode invité)
- ✅ Interface de validation des photos proposées en mode invité
- ✅ Ajout des logs dans l'onglet Système
- ✅ Ajout des stats du Raspberry (température, stockage Ram, charge processeur)

### ✅ Juin 2025

- ✅ Aperçus des photos avec suppression possible  
- ✅ Véritable mise en veille de l’écran (gestion via `wlr-randr`)  
- ✅ Paramètre de hauteur utile de l’écran (% d’écran utilisé)  
- ✅ Correction de l’orientation via EXIF et préparation des images  

 
### 💡 Idées du projet d'origine pour la suite

- 📱 Création d’une APK Android pour contrôler le cadre 
- Pimmich télécomande
- Pimmich Android TV
- Import Google Photos
- Import PhotoPrism

---

## 🔑 Récupérer le token Immich

🧭 1. Se connecter à l'interface web d’Immich

⚙️ 2. Accéder à la page "Paramètres du compte"
Une fois connecté :

Clique sur l’icône de profil (en haut à droite) ou ton nom d'utilisateur.

![Paramètre du compte](https://drive.google.com/uc?id=1_c12UZ7g8IwsL99xP55eB4qqacGAY8Kc)


Sélectionne “Account settings” ou “Paramètres du compte”.

![Menu Clef API](https://drive.google.com/uc?id=1rofAi6HNhvJbBh2D_AUsedj3HwSrQHjP)


🧪 3. Générer un nouveau token API
Dans la section "API Key" ou "Clés API" :

![Menu Clef API](https://drive.google.com/uc?id=1HrBVgvR4UXdkhLj-4KDohufr5nt57t2G)

Clique sur “Generate new API Key” ou “Générer une nouvelle clé API”.
![Menu Clef API](https://drive.google.com/uc?id=1dRBQMs0dsdM7vKlEuUzBnMmzzH3RNplc)



Donne un nom à ta clé, par exemple :
PimmichFrame

✅ Une fois générée, une clé s'affiche. C’est le token à copier.

![Menu Clef API](https://drive.google.com/uc?id=1hyt14hFPN3XEBu_0rh9XYIgLdXJau22y)

⚠️ Attention

Tu ne pourras plus voir cette clé après avoir quitté la page. Si tu la perds, il faudra en générer une nouvelle.

Ne partage jamais ce token publiquement. Il donne un accès total à tes albums Immich.

Le mieux est de créer un compte Immich réservé au cadre photo avec accès à un seul album que tu pourras alimenter à partir d'un autre compte.

---

## 📜 Licences

- **Pimmich** est distribué sous licence **MIT** (voir [LICENSE](LICENSE)) : © 2025 gotenash pour le projet d'origine, © 2026 Sweek-Adam pour les modifications de ce fork. La notice de licence d'origine est conservée.
- Les composants tiers livrés avec le projet gardent leur propre licence, dont le texte est fourni à côté de chacun :
    - Font Awesome Free (icônes CC BY 4.0, polices SIL OFL 1.1, code MIT) : `static/vendor/fontawesome/LICENSE.txt`
    - Leaflet (BSD-2-Clause), Chart.js, GLightbox, SortableJS, Tailwind CSS (MIT) : `static/vendor/*/LICENSE*`
    - Vue et Vue Router (MIT) : notices conservées dans les fichiers compilés de `static/app/`
    - Polices Caveat et Patrick Hand (SIL OFL 1.1), Permanent Marker et Special Elite (Apache 2.0) : `static/fonts/LICENSE-*.txt`
    - Contours des pays Natural Earth (domaine public) et détecteur de visages YuNet d'OpenCV Zoo (MIT) : voir `resources/README.md`
- La page `Système > Maintenance > À propos` de l'interface reprend ces crédits et licences.

---

## 💖 Crédits

- Projet d'origine : [Pimmich](https://github.com/gotenash/pimmich) par **Gotenash** et **Shenron**, réalisé dans le cadre du [Gadgetaulab](https://www.gadgetaulab.fr) — un grand merci pour ce super projet !
- Ce fork : ajouts et modifications pour un usage personnel.

<p align="center">
  <a href="https://ko-fi.com/pimmich">
    <img src="https://img.shields.io/badge/Support%20on%20Ko--fi-F16061?logo=kofi&logoColor=white" alt="Soutenir Pimmich (projet d'origine) sur Ko-fi">
  </a>
</p>
