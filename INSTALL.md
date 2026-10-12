# 🖼️ Installer Pimmich sur un Raspberry Pi neuf

> [!NOTE]
> **Ce dépôt est un fork personnel** de [Pimmich](https://github.com/gotenash/pimmich), le projet d'origine créé par Gadgetaulab.
> Il sert à un **usage purement personnel** : ce guide est fourni **tel quel**, sans garantie ni support.
> Il décrit ce que font les scripts de ce dépôt au moment où il a été écrit.

Ce guide part d'une carte SD vierge et va jusqu'à un cadre photo qui démarre tout seul. Il suppose que vous êtes à l'aise avec un terminal, mais pas que vous connaissez le projet.

🇬🇧 English version: [INSTALL_en.md](INSTALL_en.md)

---

## 📖 Sommaire

- [🧰 Matériel conseillé](#-matériel-conseillé)
- [💾 Préparer la carte SD](#-préparer-la-carte-sd)
- [🔌 Premier démarrage et connexion SSH](#-premier-démarrage-et-connexion-ssh)
- [🚀 Installer Pimmich](#-installer-pimmich)
- [🔑 Première connexion](#-première-connexion)
- [🔧 Configuration de base](#-configuration-de-base)
- [🧩 Options](#-options)
  - [Protection de la carte SD (log2ram, zram)](#protection-de-la-carte-sd-log2ram-zram)
  - [Certificat HTTPS](#certificat-https)
  - [Tailscale : lien invité à distance et HTTPS sans avertissement](#tailscale--lien-invité-à-distance-et-https-sans-avertissement)
  - [Google Drive, Dropbox, OneDrive (rclone)](#google-drive-dropbox-onedrive-rclone)
  - [Commande vocale (Picovoice)](#commande-vocale-picovoice)
  - [Spotify, AirPlay et Bluetooth](#spotify-airplay-et-bluetooth)
  - [Télévision : HDMI-CEC](#télévision--hdmi-cec)
  - [Orientation automatique (accéléromètre)](#orientation-automatique-accéléromètre)
  - [Bouton physique (GPIO)](#bouton-physique-gpio)
- [🔄 Mises à jour et sauvegarde](#-mises-à-jour-et-sauvegarde)
- [🩺 Dépannage rapide](#-dépannage-rapide)
- [❓ Pour aller plus loin](#-pour-aller-plus-loin)

---

## 🧰 Matériel conseillé

| Élément | Conseil |
|---|---|
| **Raspberry Pi** | Modèle **3B+, 4 ou 5** (ceux que recommande le README). Un Pi 4 ou 5 est plus à l'aise avec les vidéos, les dispositions et la commande vocale. |
| **Alimentation** | L'alimentation officielle, ou une alimentation de même puissance : **Pi 5** : 5,1 V / 5 A (USB-C, 27 W) ; **Pi 4** : 5,1 V / 3 A (USB-C, 15 W) ; **Pi 3B+** : 5,1 V / 2,5 A (micro-USB). Ce sont les valeurs que Pimmich indique dans `Système > Maintenance > Matériel`, qui signale aussi une alimentation insuffisante. |
| **Carte SD** | **32 Go minimum**, classe **A1 ou A2**. Prévoyez plus grand si vous gardez beaucoup de photos et de vidéos sur la carte (un disque USB ou un NAS peut aussi les accueillir). |
| **Écran** | Un écran HDMI ou une télévision. Les Pi 4 et 5 ont des prises **micro-HDMI** : il faut un câble ou un adaptateur micro-HDMI → HDMI. |
| **Réseau** | Wi-Fi ou câble Ethernet, avec un accès à Internet pendant l'installation. |
| *Option* : **accéléromètre I2C** | MPU-6050, ADXL345 ou LIS3DH (quelques euros), pour que l'écran pivote tout seul quand on tourne le cadre. Voir [Orientation automatique](#orientation-automatique-accéléromètre). |
| *Option* : **micro USB** | Pour la commande vocale. Voir [Commande vocale](#commande-vocale-picovoice). |
| *Option* : **son** | Le son sort par l'HDMI (haut-parleurs de l'écran ou de la TV) ou par la prise jack 3,5 mm (Pi 3B+ et Pi 4 ; le Pi 5 n'en a pas). |

---

## 💾 Préparer la carte SD

1. Sur un ordinateur, installez **Raspberry Pi Imager** (<https://www.raspberrypi.com/software/>) et lancez-le.
2. Choisissez votre modèle de Raspberry Pi, puis le système **Raspberry Pi OS (64-bit)**, la version **avec bureau** basée sur **Debian 13 « Trixie »** : c'est la version recommandée par le README.
   > La version *Lite* (sans bureau) n'est pas celle recommandée. Le bouton `Système > Maintenance > Repasser sur Raspberry Pi OS (bureau)` a d'ailleurs besoin du bureau pour fonctionner.
3. Choisissez la carte SD.
4. Remplissez les **réglages de personnalisation**. Selon la version d'Imager, ils apparaissent dans un assistant ou derrière le bouton « Modifier réglages » :
   - **Nom d'hôte** : par exemple `cadre`. Le Pi sera alors joignable à l'adresse `cadre.local`, et ce nom figurera dans le certificat HTTPS créé à l'installation.
   - **Nom d'utilisateur et mot de passe** : vous choisissez librement (voir l'encadré ci-dessous). Ce mot de passe est celui du compte Linux (SSH et `sudo`), pas celui de l'interface Pimmich.
   - **Wi-Fi** : nom du réseau (SSID), mot de passe et pays.
   - **Fuseau horaire et clavier**. Le fuseau horaire sera de toute façon réglé de nouveau par `setup.sh` (voir [ce que fait setup.sh](#3-ce-que-fait-setupsh)).
   - **SSH** : activez-le, avec un mot de passe ou une clé publique.
5. Écrivez la carte, puis insérez-la dans le Raspberry Pi.

> [!IMPORTANT]
> **Nom d'utilisateur et dossier : ce qu'attendent les scripts**
> - **Le nom d'utilisateur est libre** : aucun script n'impose `pi`.
> - `setup.sh` retrouve votre utilisateur avec la commande `logname`. Lancez-le donc depuis **votre session normale** (de préférence en SSH), précédé de `sudo`, mais **pas** depuis un shell root (`sudo su`, `sudo -i`) ni connecté directement en root : sinon tout serait configuré pour root.
> - C'est à cet utilisateur que sont donnés les dossiers de données (`static`, `logs`, `cache`, `config`) et les droits `sudo` ciblés (`/etc/sudoers.d/pimmich-auth`). C'est aussi dans son dossier personnel que sont écrits `~/.bash_profile` et `~/.config/sway/config`, qui lancent le cadre au démarrage.
> - `setup.sh` active la connexion automatique en console (via `raspi-config`). Installez Pimmich avec **le compte créé dans Imager** (le premier compte du système) : la session ouverte automatiquement au démarrage sera ainsi bien celle où le cadre est configuré.
> - **Dossier** : clonez le dépôt dans **`~/pimmich`**. Les scripts fonctionnent depuis n'importe quel dossier, mais les commandes affichées par l'interface et par la FAQ supposent `~/pimmich`. Surtout, le chemin complet de `start_pimmich.sh` est écrit dans la configuration de Sway au moment de l'installation : **ne déplacez pas le dossier ensuite**.

---

## 🔌 Premier démarrage et connexion SSH

1. Branchez l'écran (et le câble réseau si vous en utilisez un), puis l'alimentation. Le premier démarrage prend quelques minutes, car Raspberry Pi OS termine sa configuration et peut redémarrer tout seul une fois. Le bureau finit par s'afficher.
2. Depuis votre ordinateur, connectez-vous en SSH avec le nom d'utilisateur et le nom d'hôte choisis dans Imager :
   ```bash
   ssh utilisateur@cadre.local
   ```
   Si le nom `cadre.local` n'est pas trouvé, utilisez l'adresse IP du Pi : elle est indiquée dans l'interface de votre box, ou s'obtient avec `hostname -I` dans un terminal sur le Pi.
3. **Mettez le système à jour.** `setup.sh` rafraîchit seulement la liste des paquets (`apt update`) : il ne met pas à jour les paquets déjà installés.
   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   sudo reboot
   ```
4. Reconnectez-vous en SSH une fois le Pi redémarré.

---

## 🚀 Installer Pimmich

### 1. Récupérer le code

Clonez le dépôt **sans `sudo`**, pour que les fichiers appartiennent à votre utilisateur :

```bash
cd ~
git clone https://github.com/Sweek-Adam/Pimmich-fork.git pimmich
cd pimmich
```

`git` est normalement déjà présent sur Raspberry Pi OS. S'il manque, installez-le avec `sudo apt install -y git`.

### 2. Lancer le script d'installation

Vérifiez d'abord que `logname` affiche bien votre nom d'utilisateur, puisque c'est lui que `setup.sh` utilise :

```bash
logname
```

Lancez ensuite l'installation :

```bash
chmod +x setup.sh
sudo ./setup.sh
```

- **Aucune question n'est posée** : le script ne demande rien et n'a pas d'option.
- **Durée** : comptez de l'ordre de **20 à 45 minutes**. C'est une estimation : la durée dépend surtout du modèle de Pi, de la carte SD et du débit Internet. Le plus long est l'installation des bibliothèques Python et le téléchargement des modèles de reconnaissance vocale.
- **Il faut Internet pendant toute l'installation.** Si le script s'arrête sur une erreur (réseau coupé, par exemple), relancez simplement `sudo ./setup.sh`. Il est prévu pour être relancé : les étapes déjà faites sont reconnues et sautées.

> [!WARNING]
> **Notez le mot de passe affiché à l'étape 8/12.** Un encadré « NOTEZ CES IDENTIFIANTS, ILS NE SERONT PLUS AFFICHÉS » indique l'utilisateur (`admin`) et un mot de passe aléatoire de 12 caractères. **C'est la seule fois où ce mot de passe apparaît en clair.** Si vous le perdez, voyez la [Première connexion](#-première-connexion) pour en générer un nouveau.

### 3. Ce que fait setup.sh

| Étape | Ce qui se passe |
|---|---|
| 1/12 | `apt update` (liste des paquets). |
| 2/12 | Installe les paquets système : `sway`, `xterm`, `python3`, `python3-venv`, `python3-pip`, `libjpeg-dev`, `libopenjp2-7-dev`, `libtiff-dev`, `libopenblas-dev`, `ffmpeg`, `git`, `cifs-utils`, `smbclient`, `network-manager`, `jq`, `mpv`, `gettext`, `portaudio19-dev` (ou `libportaudio-dev` à défaut), `unzip`, `libheif-dev`. Active ensuite la langue `fr_FR.UTF-8`, pour que les dates s'affichent en français. |
| 3/12 | Installe `python3-rpi.gpio`. Désactive l'économie d'énergie du Wi-Fi (fichier `/etc/NetworkManager/conf.d/99-disable-wifi-powersave.conf`), qui provoque des décrochages, puis redémarre NetworkManager. |
| 4/12 | Détecte le fuseau horaire d'après l'adresse IP publique (service `ip-api.com`) et l'applique avec `timedatectl`, ou règle UTC si la détection échoue. **Ce réglage remplace celui choisi dans Imager.** |
| 5/12 | Installe **nginx**, supprime son site par défaut et lance `utils/enable_https.sh`. Ce script crée un certificat auto-signé valable 10 ans dans `/etc/ssl/pimmich/`, pour le nom d'hôte, `nom.local` et les adresses IP du moment. Il écrit aussi le site `/etc/nginx/sites-available/pimmich` : HTTP (port 80) redirige vers HTTPS (port 443), sauf la page d'envoi des invités, qui reste aussi accessible en HTTP. Pimmich lui-même n'écoute qu'en local (`127.0.0.1:5000`). |
| 6/12 | Crée l'environnement Python `venv/` dans le dossier du projet et y installe `requirements.txt`, `qrcode` et `python-telegram-bot`. **Sur Pi 3 et plus**, ajoute `pillow-heif` (photos HEIC d'iPhone), les bibliothèques de la commande vocale (Vosk, Porcupine…), le modèle de langue français de Porcupine, le son `static/sounds/ding.wav` et les modèles Vosk français et anglais (dossier `models/`). Sur Pi 1, Pi 2 et Zero, cette partie vocale est sautée. |
| 7/12 | Crée `logs/`, `cache/`, `static/photos/`, `static/prepared/`, `static/pending_uploads/` et `config/`, puis les donne à votre utilisateur. |
| 8/12 | Si `/boot/firmware/credentials.json` n'existe pas encore, crée le compte administrateur **`admin`** avec un mot de passe aléatoire (affiché une seule fois). Crée aussi la règle `/etc/sudoers.d/pimmich-auth`, qui autorise sans mot de passe uniquement : écrire ce fichier, `reboot`, `shutdown`, `nmcli`, `raspi-config`, `mount`, `umount` et `timedatectl`. |
| 9/12 | Configure le démarrage en **console avec connexion automatique** (`raspi-config nonint do_boot_behaviour B2`). Le bureau ne s'affiche plus. |
| 10/12 | Ajoute à `~/.bash_profile` le lancement de **Sway** sur la console `tty1`. |
| 11/12 | Ajoute à `~/.config/sway/config` la ligne `exec_always --no-startup-id <dossier>/start_pimmich.sh`, ainsi que des règles qui affichent en plein écran les vidéos (`mpv`) et le diaporama. |
| 12/12 | Fin : « Redémarrez pour lancer automatiquement Sway + Pimmich. » |

> [!NOTE]
> Il n'y a **pas de service systemd** pour Pimmich. Au démarrage, la connexion automatique sur `tty1` lance Sway, qui lance `start_pimmich.sh`, qui lance l'application (`app.py`). `start_pimmich.sh` relance l'application si elle s'arrête et écrit tout dans `logs/pimmich.log`.

### 4. Redémarrer

```bash
sudo reboot
```

Au démarrage, la console se connecte toute seule, puis Sway et Pimmich se lancent. Pendant les heures d'affichage (**7 h – 22 h par défaut**), le cadre affiche le logo, « Aucune photo trouvée. », l'adresse `Configurez sur : http://<IP>` et un **QR code**. En dehors de ces heures, l'écran reste noir, et c'est normal.

---

## 🔑 Première connexion

1. Sur un téléphone ou un ordinateur connecté au même réseau, **scannez le QR code**, ou tapez l'adresse affichée (`http://<IP>`) ou `http://cadre.local`. nginx vous redirige automatiquement vers **`https://`**.
2. Le certificat est **auto-signé** : le navigateur affiche un avertissement la première fois. Acceptez-le une fois sur chaque appareil (« Paramètres avancés » puis « Continuer », selon le navigateur). Pour une adresse sans avertissement, voyez [Tailscale](#tailscale--lien-invité-à-distance-et-https-sans-avertissement).
3. Connectez-vous avec l'utilisateur **`admin`** et le mot de passe noté à l'étape 8/12.

> [!NOTE]
> **À propos de `/boot/firmware/credentials.json`.** Ce fichier se trouve sur la partition de démarrage, celle que l'on voit en branchant la carte SD sur un ordinateur ; c'est pourquoi l'écran du cadre parle de « credentials.json à la racine de la SD ». Il contient le nom d'utilisateur, mais le mot de passe n'y est stocké que **sous forme hachée** (`password_hash`), à côté de la clé secrète des sessions. **On ne peut donc pas y relire le mot de passe.**
> ```bash
> sudo cat /boot/firmware/credentials.json
> ```
> Cette commande affiche tout le fichier : ne le partagez pas, il contient la clé secrète des sessions. Pour voir seulement le nom d'utilisateur, utilisez `jq` (installé par `setup.sh`) :
> ```bash
> sudo jq -r .username /boot/firmware/credentials.json
> ```

**Mot de passe perdu ou pas noté ?** Si un autre compte administrateur existe, il peut réinitialiser votre mot de passe dans `Système > Comptes`. Sinon, régénérez le fichier d'identification : un nouveau mot de passe s'affiche une fois dans le terminal. C'est la commande que Pimmich indique lui-même dans ses journaux.

```bash
cd ~/pimmich
sudo venv/bin/python utils/create_initial_user.py --output /boot/firmware/credentials.json
```

La [FAQ](FAQ.md) propose une autre méthode : supprimer le fichier avec `sudo rm /boot/firmware/credentials.json`, puis relancer `sudo ./setup.sh`.

4. **Changez le mot de passe tout de suite** : `Système > Comptes`, carte « Mon compte », champs « Nouveau mot de passe » et « Confirmer le mot de passe », puis « Changer le mot de passe ».
5. **Les interfaces.** Après la connexion, c'est la **nouvelle interface** (`/app`) qui s'ouvre. Son menu a cinq rubriques (Accueil, Photos, Écran, Partage, Système) ; elle est adaptée au téléphone et propose une recherche et une visite guidée. L'**interface classique** (`/configure`) reste accessible par le lien « Interface classique » en bas du menu, et le choix est mémorisé dans le navigateur. Tous les réglages sont disponibles dans la nouvelle interface. La langue de l'interface suit celle du navigateur (français, anglais, espagnol, allemand ou japonais).

---

## 🔧 Configuration de base

L'**Accueil** affiche une liste « **Bien démarrer** » qui suit vos progrès : choisir une source de photos, importer des photos, régler les heures d'affichage, choisir une ambiance, inviter la famille, sécuriser la connexion (HTTPS, déjà fait par `setup.sh`) et activer la sauvegarde automatique. La carte « **État du cadre** » signale les problèmes, avec un lien vers la page à corriger. Dans la nouvelle interface, les réglages s'enregistrent automatiquement, et le diaporama est relancé tout seul après une série de changements.

### 1. Ajouter une source : `Photos > Sources`

- **Immich** : renseignez l'URL du serveur (par exemple `http://192.168.1.YY:2283`), le token d'accès (voir [Récupérer le token Immich](README.md#-récupérer-le-token-immich)) et le nom technique de l'album. Vous pouvez activer la mise à jour automatique et choisir son intervalle.
- **Samba / partage Windows** : renseignez le serveur, le nom du partage, et si besoin un chemin, un utilisateur et un mot de passe. Le bouton « Tester la connexion Samba » vérifie l'accès.
- **Google Drive, autres clouds, albums partagés iCloud, photos par e-mail** : suivez l'assistant de chaque carte. Google Drive et les autres clouds sont détaillés [plus bas](#google-drive-dropbox-onedrive-rclone).
- Cochez enfin la source dans « **Sources à afficher dans le diaporama** ». Par défaut, seule Immich est cochée.

### 2. Importer : `Photos > Importer`

- Carte « Importation des photos » : les boutons « Importer depuis Immich », « Importer depuis Samba », « Importer depuis Google Drive » et « Importer depuis la clé USB » lancent un import. Pour la clé USB, branchez-la d'abord sur le Pi. La progression s'affiche pendant l'import, puis pendant la préparation des photos aux dimensions de l'écran ; le diaporama redémarre ensuite.
- « **Importer depuis un Smartphone** » ouvre la page d'envoi depuis le navigateur du téléphone.
- « **Importer une discussion WhatsApp** » accepte le `.zip` exporté depuis WhatsApp.
- Les photos reçues par **Telegram** (`Partage > Telegram`) sont importées automatiquement.

### 3. Régler les heures d'affichage : `Écran > Affichage`

- Cartes « **Horaires Semaine (Lun-Ven)** » et « **Horaires Weekend (Sam-Dim)** » : heures d'allumage et d'extinction. Par défaut, le cadre s'affiche de 7 h à 22 h.
- Carte « **Le soir et la nuit** » : baisse de luminosité le soir et, en dehors des heures d'affichage, écran éteint ou horloge de nuit.
- La même page règle aussi la durée d'affichage, les transitions et les vidéos (son, sortie audio, décodage matériel), ainsi que la télévision (HDMI-CEC).

### 4. Pour le reste

- **`Écran > Horloge & météo`** : heure, date, météo (clé OpenWeatherMap), marées, agenda Google et comptes à rebours.
- **`Écran > Dispositions`** : mosaïque, mur, magazine… et leur fréquence.
- **`Partage > Invités`** : QR code et page d'envoi pour les proches connectés au même Wi-Fi (photos, messages, dessins, messages vocaux, réactions). Les photos des invités passent par `Partage > À valider`.
- **`Système > Réseau`** : Wi-Fi et interface filaire.
- **`Système > Comptes`** : comptes des membres de la famille.

---

## 🧩 Options

Chaque option ci-dessous est facultative et se met en place une seule fois, en SSH sur le Pi. Les scripts se trouvent dans `~/pimmich/utils/`.

### Protection de la carte SD (log2ram, zram)

```bash
sudo ~/pimmich/utils/enable_sd_protection.sh
sudo reboot
```

- Installe **log2ram** depuis le dépôt de son auteur (ajout de la source `packages.azlux.fr` à apt). Les journaux du système (`/var/log`) et de Pimmich (`~/pimmich/logs`) sont alors écrits en mémoire vive (128 Mo), puis recopiés sur la carte une fois par jour et à l'arrêt.
- Limite la taille et la durée de conservation des journaux de `journald` (40 Mo, 2 semaines).

Avec l'option **`--zram`**, le fichier d'échange (swap) sur la carte est en plus remplacé par une mémoire d'échange compressée en RAM. Le script passe par `rpi-swap` s'il est présent, sinon par `zram-tools`. Les lignes de swap de `/etc/fstab` sont mises en commentaire, avec une sauvegarde dans `/etc/fstab.bak`.

```bash
sudo ~/pimmich/utils/enable_sd_protection.sh --zram
sudo reboot
```

Pour vérifier que la protection est active : `Système > Maintenance`, carte « Système de Fichiers de la Carte SD », rubrique « Protection contre l'usure ».

### Optimiser Raspberry Pi OS pour le cadre

```bash
sudo ~/pimmich/utils/optimize_pi.sh --dry-run   # aperçu : ce qui serait changé
sudo ~/pimmich/utils/optimize_pi.sh             # applique, puis : sudo reboot
sudo ~/pimmich/utils/optimize_pi.sh --undo      # revient à la configuration d'origine
```

Le script désactive ce qui ne sert pas à un cadre photo : cloud-init (utile seulement au premier démarrage, environ 10 s gagnées à chaque démarrage), l'attente du réseau au démarrage, les mises à jour automatiques du système (remplacées par celles de 4 h 30, voir plus bas), l'index des pages de manuel, NFS et l'impression. Il regroupe aussi les écritures sur la carte SD et retire la détection de caméra et l'écran arc-en-ciel du démarrage (`config.txt` est sauvegardé avant). Le bureau, l'enceinte Bluetooth et `cadre.local` ne sont pas touchés.

### Certificat HTTPS

`setup.sh` a déjà lancé `utils/enable_https.sh` : l'interface est en HTTPS dès l'installation. Si le **nom d'hôte** ou l'**adresse IP** du cadre change, recréez le certificat pour qu'il couvre la nouvelle adresse :

```bash
sudo ~/pimmich/utils/enable_https.sh --renew
```

Sans `--renew`, le script garde le certificat existant et réécrit seulement la configuration nginx. C'est utile si l'**État du cadre** affiche l'alerte « Connexion non chiffrée ».

### Tailscale : lien invité à distance et HTTPS sans avertissement

Tailscale n'est **pas** installé par `setup.sh`.

1. Installez Tailscale en suivant <https://tailscale.com/download/linux>, puis connectez le cadre à votre compte :
   ```bash
   sudo tailscale up
   ```
2. Lancez une fois le script de préparation. Inutile de le préfixer de `sudo` : il demande lui-même le mot de passe quand il en a besoin.
   ```bash
   ~/pimmich/utils/enable_remote_guests.sh
   ```
   Il crée une entrée nginx locale (`127.0.0.1:8088`) qui ne laisse passer **que** la page d'envoi des invités. Il autorise aussi le compte de Pimmich à piloter Tailscale (`tailscale set --operator`), pour que l'interface puisse activer ou couper les publications.
3. **Lien invité depuis l'extérieur** : `Partage > Invités`, carte « Hors de la maison », puis « Autoriser les envois depuis l'extérieur ». La première fois, Tailscale peut demander d'autoriser Funnel (bouton « Autoriser Funnel sur Tailscale »). Utilisez ensuite « Partager le lien » ; « Changer le lien » rend l'ancien inutilisable. L'administration et vos photos ne sont jamais publiées, et les photos des invités passent toujours par « À valider ».
4. **Administration en HTTPS sans avertissement** : `Système > Maintenance`, carte « HTTPS sans avertissement (Tailscale) », puis « Activer l'accès HTTPS par Tailscale ». L'administration devient joignable à une adresse `https://…ts.net:8443`, avec un vrai certificat, **seulement depuis vos appareils connectés à Tailscale** : elle n'est jamais publiée sur Internet. Si Tailscale le demande, autorisez d'abord les certificats HTTPS sur votre compte (bouton « Autoriser sur Tailscale »).

### Google Drive, Dropbox, OneDrive (rclone)

`rclone` n'est **pas** installé par `setup.sh`.

**Google Drive** propose deux méthodes, au choix dans `Photos > Sources`, carte Google Drive, réglage « Méthode de connexion » :

- **Compte de service Google** (sans rclone) : créez un compte de service dans la console Google Cloud, avec l'API Google Drive activée. Téléchargez sa clé JSON et collez-la dans la carte. Partagez ensuite vos dossiers de photos avec l'adresse e-mail du compte de service.
- **rclone** : installez rclone sur le Pi, par exemple avec le paquet Debian (`sudo apt install rclone`) ou selon la méthode de <https://rclone.org>. Créez ensuite un « remote » Google Drive **avec votre utilisateur habituel, sans `sudo`**, puisque Pimmich lit la configuration rclone du compte qui le fait tourner :
  ```bash
  rclone config
  ```
  Sur un cadre sans navigateur, l'assistant de rclone propose de terminer l'autorisation depuis un ordinateur. Dans la carte Google Drive, choisissez ensuite le remote, puis cliquez sur « Afficher mes dossiers Google Drive » et cochez les dossiers à afficher.

**Autres clouds** (Dropbox, OneDrive, pCloud…) : carte « Autres clouds », puis « Ajouter un compte ». Sur un ordinateur avec un navigateur, installez rclone et lancez la commande affichée, par exemple `rclone authorize "dropbox"`. Collez ensuite dans la carte le texte affiché entre accolades. Pimmich crée alors le compte rclone sur le cadre, ce qui suppose que **rclone soit aussi installé sur le Pi**.

La **sauvegarde automatique sur Google Drive** (`Système > Maintenance`) passe elle aussi par une connexion rclone.

### Commande vocale (Picovoice)

**Prérequis** : un micro USB et un Pi 3 ou plus récent. Sur ces modèles, `setup.sh` a déjà installé Vosk, Porcupine et les modèles de langue. Une **clé d'accès Picovoice** (AccessKey) est nécessaire : le code actuel l'exige dans tous les cas, même si le moteur « Vosk » est sélectionné dans l'interface.

1. Créez un compte gratuit sur la **Picovoice Console** et copiez votre AccessKey.
2. **Mot-clé** : le dépôt fournit déjà `voice_models/cadre-magique_raspberry-pi.ppn` (« Cadre Magique », en français). Pour utiliser le vôtre, ou pour l'anglais, créez un mot-clé dans la section *Porcupine* de la console et téléchargez-le pour la plateforme **Raspberry Pi**. Renommez-le en `cadre-magique_raspberry-pi.ppn` (français) ou `magic-frame_raspberry-pi_en.ppn` (anglais), puis copiez-le dans `~/pimmich/voice_models/`, par exemple depuis votre ordinateur :
   ```bash
   scp cadre-magique_raspberry-pi.ppn utilisateur@cadre.local:~/pimmich/voice_models/
   ```
   Si le fichier fourni est refusé avec votre clé (voir les journaux), générez le vôtre comme ci-dessus.
   > Le fichier français fait partie du dépôt. Une mise à jour depuis l'interface (qui fait un `git reset --hard`) le remet donc à la version du dépôt : gardez une copie du vôtre.
3. Dans `Système > Commande vocale`, réglez :
   - la langue de reconnaissance ;
   - la clé d'accès Picovoice ;
   - le microphone (« Périphérique d'entrée audio ») ;
   - testez avec « Diagnostic Audio », puis « Lancer le diagnostic ».

   Cochez enfin « Activer le contrôle vocal ».
4. Les commandes disponibles sont listées dans le [README](README.md#️-contrôle-vocal). En cas de souci, consultez `Système > Journaux`, où les journaux de `voice_control.py` apparaissent.

### Spotify, AirPlay et Bluetooth

Ce script fait du cadre une enceinte **Spotify Connect** (compte Premium), un récepteur **AirPlay** et une enceinte **Bluetooth**. Lancez-le une fois depuis le compte qui fait tourner Pimmich, **sans `sudo`** : il demande lui-même le mot de passe pour installer les paquets.

```bash
~/pimmich/utils/enable_music_receivers.sh
```

Le script :
- installe `librespot` (via le paquet raspotify, téléchargé depuis `dtcooper.github.io`), `shairport-sync`, `playerctl`, `rfkill`, `python3-dbus` et `python3-gi` ;
- configure le Bluetooth en enceinte ;
- crée et active les services utilisateur `pimmich-spotify`, `pimmich-airplay`, `pimmich-airplay-meta`, `pimmich-bluetooth` et `pimmich-bt-mpris` ;
- active `loginctl enable-linger`, pour que ces services démarrent avec le cadre.

Le cadre apparaît ensuite sous le nom « **Cadre photo** ». La page `Écran > Son`, carte « Le cadre comme enceinte », affiche l'état de chaque service et permet d'associer un téléphone Bluetooth (bouton « Associer un téléphone », pendant 3 minutes). Elle permet aussi de connecter Spotify pour le piloter depuis l'interface.

Pour vérifier un service, par exemple : `systemctl --user status pimmich-spotify`.

### Télévision : HDMI-CEC

Dans `Écran > Affichage`, carte « Télévision », activez « **Piloter la télévision par HDMI-CEC** » : la TV s'allume sur l'entrée du cadre au réveil et se met en veille avec lui. Activez aussi le HDMI-CEC dans les réglages de la TV (Anynet+, Bravia Sync, SimpLink…).

Pimmich utilise la commande `cec-ctl` (paquet `v4l-utils`) et le périphérique `/dev/cec0`. Si `command -v cec-ctl` ne renvoie rien, installez le paquet :

```bash
sudo apt install v4l-utils
```

### Orientation automatique (accéléromètre)

1. Branchez un accéléromètre I2C (MPU-6050, ADXL345 ou LIS3DH) sur les broches **SDA, SCL, 3,3 V et GND** du Pi, et fixez-le au dos du cadre.
2. Activez l'I2C : `sudo raspi-config`, menu *Interface Options › I2C*.
3. Dans `Écran > Affichage`, carte « Écran », réglez « Orientation du cadre » sur « Automatique (capteur d'orientation) ». La carte « Résolution de l'écran » affiche alors l'état du capteur. Mémorisez ensuite les positions : posez le cadre en paysage et cliquez sur « Le cadre est en paysage », puis posez-le en portrait et cliquez sur « Le cadre est en portrait ».

La bibliothèque I2C (`smbus2`) est déjà installée par `requirements.txt`.

### Bouton physique (GPIO)

Le code du diaporama sait gérer un bouton de mise en veille (GPIO 23 par défaut, relié à la masse). Mais aucune page de l'interface actuelle ne permet de l'activer : cette option n'est donc pas couverte par ce guide.

---

## 🔄 Mises à jour et sauvegarde

### Mettre à jour depuis l'interface (recommandé)

`Système > Maintenance`, carte « **Mise à jour de l'application** » : elle affiche la version installée et les changements disponibles. Cliquez sur « **Lancer la mise à jour** », puis suivez la page de progression. Le script `update_script.sh` :

1. sauvegarde `config/`, puis fait `git fetch` et `git reset --hard origin/main` : **toute modification locale des fichiers du dépôt est perdue**, mais `config/` est restauré ;
2. met à jour les dépendances Python. En cas d'échec, un avertissement s'affiche et le détail est dans `logs/update_pip.log` ;
3. redémarre Pimmich, sans redémarrer le Pi.

**Retour arrière automatique** : si la nouvelle version plante 3 fois de suite dans les 90 secondes après son lancement, `start_pimmich.sh` revient tout seul à la version précédente. La nouvelle version est validée après environ 2 minutes de fonctionnement normal. Le bouton « **Revenir à la version précédente** » permet aussi de revenir en arrière à la main.

### Mise à jour automatique chaque nuit (crontab)

Pour que le cadre se mette à jour tout seul, chaque jour à 4 h 30 :

```bash
~/pimmich/utils/enable_auto_update.sh            # Pimmich seulement
~/pimmich/utils/enable_auto_update.sh --system   # Pimmich + paquets du système (demande le mot de passe une fois)
```

- Lancez-le **sans `sudo`**. Il ajoute une ligne à votre crontab (`crontab -l` pour la voir) ; `--time 03:15` choisit une autre heure, `--off` coupe la mise à jour automatique.
- Chaque nuit, `utils/auto_update.sh` regarde s'il y a du nouveau sur GitHub. Si oui, il fait la même mise à jour que le bouton de l'interface, puis relance Pimmich. Si la nouvelle version plante au démarrage, Pimmich revient tout seul à la précédente.
- Avec `--system`, les paquets du système sont aussi mis à jour (`apt-get upgrade`, puis `apt-get autoremove` pour retirer les paquets devenus inutiles), sans redémarrage automatique. Le journal signale quand un redémarrage est conseillé.
- Rien n'est fait pendant une synchronisation (rclone) ou une autre mise à jour : ce sera pour la nuit suivante.
- Journal : `~/pimmich/logs/auto_update.log`.

### Mettre à jour en SSH (`git pull`)

```bash
cd ~/pimmich
git pull
sudo reboot
```

Si `requirements.txt` a changé, mettez aussi à jour les dépendances Python avant de redémarrer, comme le fait `update_script.sh`. `setup.sh` donne l'environnement `venv/` à votre utilisateur : pas besoin de `sudo`. (Sur une installation faite avant cette correction, `venv/` peut appartenir à root : rendez-le-vous une fois avec `sudo chown -R "$USER:$USER" venv`.)

```bash
venv/bin/pip install -r requirements.txt
```

Au lieu de `sudo reboot`, vous pouvez aussi utiliser `Système > Maintenance > Redémarrer l'application web`. Node.js n'est pas nécessaire : la nouvelle interface est livrée déjà compilée dans `static/app/`.

### Sauvegarde complète

`Système > Maintenance`, carte « **Sauvegarde complète** » :

- « **Sans les photos** », puis « **Télécharger** » : vous obtenez un fichier `.zip` qui contient les réglages (dossier `config/`), les comptes, les playlists, les messages, dessins et messages vocaux, le livre d'or, les légendes, les réactions, la musique et l'historique. « Restaurer ce fichier » le réapplique, sur ce cadre ou sur une nouvelle installation. **Gardez ce fichier en lieu sûr** : `config/` contient vos clés et jetons d'accès (Immich, météo…).
- « **Avec les photos, sur un disque USB ou un NAS** » : ajoutez d'abord un support dans la carte « Stockage des photos ».
- « **Sauvegarde automatique sur Google Drive** » : réglages seulement, sans les photos, par une connexion rclone.

Deux éléments ne sont **pas** dans la sauvegarde : le mot de passe `admin` (`/boot/firmware/credentials.json`, hors du dossier du projet) et les identifiants Spotify (`~/.config/pimmich`). Après une restauration sur une nouvelle installation, connectez-vous donc avec le mot de passe `admin` de cette nouvelle installation.

---

## 🩺 Dépannage rapide

### Où trouver les journaux

- **`Système > Journaux`** : le journal « Pimmich (Serveur Web & Supervisor) » correspond à `logs/pimmich.log` et regroupe l'application web, le diaporama et le script de démarrage. Les journaux de la commande vocale apparaissent aussi s'ils existent. La page propose un filtre « Erreurs seulement » et un « Suivre en direct ».
- **`Système > Maintenance`**, carte « Matériel » : température, alimentation (signale une tension insuffisante) et erreurs de la carte SD.
- **En SSH** :
  ```bash
  tail -f ~/pimmich/logs/pimmich.log
  ```
  Autres fichiers utiles : `~/pimmich/logs/update_pip.log` (dépendances lors d'une mise à jour) et `/tmp/mpv_pimmich.log` (lecteur vidéo, effacé au redémarrage). Avec log2ram, `logs/` est en mémoire vive mais reste au même endroit.

### Redémarrer Pimmich

Pimmich n'a pas de service systemd : il est lancé par Sway via `start_pimmich.sh`, qui le relance s'il s'arrête.

- **Depuis l'interface** : `Système > Maintenance`, carte « Contrôle du système ». « Redémarrer l'application web » ne relance que l'application ; « Redémarrer le système » redémarre le Pi.
- **En SSH** : le plus simple est `sudo reboot`. Vous pouvez aussi arrêter l'application : `start_pimmich.sh` la relance environ 5 secondes plus tard.
  ```bash
  pkill -f "python3 -u app.py"
  ```
- **nginx** : `sudo nginx -t` vérifie sa configuration, et `sudo systemctl restart nginx` le redémarre. Pendant un redémarrage de Pimmich, nginx affiche une page d'attente au lieu d'une erreur 502.

### Écran noir

- **Heures d'affichage** : en dehors des heures réglées dans `Écran > Affichage` (7 h – 22 h par défaut), l'écran est éteint, ou affiche l'horloge de nuit si vous l'avez choisie. L'Accueil indique « Le cadre est en veille » et propose « Allumer le cadre ».
- **Sway ne démarre pas** (vous voyez une console texte ou une invite de connexion) : vérifiez que la connexion automatique se fait bien avec le compte qui a installé Pimmich (`sudo raspi-config`, menu *System Options*). Vérifiez aussi que les lignes de lancement sont présentes :
  ```bash
  grep -n "exec sway" ~/.bash_profile
  grep -n "start_pimmich" ~/.config/sway/config
  ```
- **Résolution** : au démarrage, Pimmich impose la résolution enregistrée (1920 × 1080 par défaut). Si votre écran ne la gère pas, changez-la dans `Écran > Affichage`, carte « Résolution de l'écran » (« Voir les résolutions de l'écran », puis « Appliquer »).
- **Écran noir ou bleu après une vidéo** : décochez « Activer le décodage vidéo matériel » dans `Écran > Affichage`, carte « Vidéos ».
- **Alimentation** : si `Système > Maintenance > Matériel` signale une alimentation insuffisante, changez d'alimentation (voir le [matériel conseillé](#-matériel-conseillé)).
- **L'écran ne s'éteint pas complètement la nuit** : voir la [FAQ](FAQ.md) (HDMI-CEC ou prise connectée).

### Pas de son HDMI

- Dans `Écran > Affichage`, carte « Vidéos », vérifiez « Activer le son pour les vidéos », la « Sortie audio » (Automatique ou HDMI) et le volume. Vérifiez aussi le volume de l'écran ou de la TV.
- Si l'écran ou la TV était éteint au démarrage du Pi, le son HDMI peut disparaître. Pimmich vérifie toutes les 5 minutes et le répare tout seul dès que l'écran répond ; sinon, redémarrez le Pi avec l'écran allumé.
- Pour la prise jack, choisissez « Jack 3.5mm » (pas disponible sur Pi 5).

### Wi-Fi

- **`Système > Réseau`** : la page affiche l'état de la connexion, le réseau et l'adresse IP. La carte « Configuration Wi-Fi » (pays, SSID, mot de passe) change de réseau, ce qui peut couper la connexion au cadre une minute. La liste des réseaux à proximité y est aussi.
- L'économie d'énergie du Wi-Fi, qui provoque des décrochages, est déjà désactivée par `setup.sh`.
- Si un câble Ethernet est branché, il est prioritaire : désactivez temporairement l'« Interface Filaire (eth0) » pour forcer le Wi-Fi.
- Si l'adresse IP du cadre change, utilisez plutôt `https://cadre.local`, et pensez à [renouveler le certificat](#certificat-https).

### Autres cas

- **« Trop de tentatives de connexion »** : après plusieurs mots de passe erronés, la connexion est bloquée quelques minutes. Patientez, puis réessayez.
- **Mauvaise heure** : corrigez le fuseau horaire, par exemple `sudo timedatectl set-timezone Europe/Paris`.
- **Revenir au bureau Raspberry Pi OS** : `Système > Maintenance > Repasser sur Raspberry Pi OS (bureau)`. Pour revenir ensuite au mode cadre photo, double-cliquez sur le raccourci **« Revenir au cadre Pimmich »** (sur le bureau ou dans le menu des applications) : il demande confirmation puis redémarre le Pi en mode cadre. En SSH : `~/pimmich/utils/switch_to_pimmich.sh --yes`. Pendant que le bureau est affiché, l'interface d'administration reste accessible (sans diaporama) : `Système > Maintenance` indique le mode actuel et propose aussi « Repasser sur Pimmich (cadre photo) ».

---

## ❓ Pour aller plus loin

- **FAQ** : [FAQ.md](FAQ.md) (en anglais : [FAQ_en.md](FAQ_en.md)), pour le Wi-Fi, l'affichage, les vidéos, les invités, Telegram, les mises à jour…
- **README** : [README.md](README.md), pour les fonctionnalités, les commandes vocales et le token Immich.
