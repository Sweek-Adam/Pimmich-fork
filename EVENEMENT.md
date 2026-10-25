# Pimmich « événement » : le cadre photo sur un ordinateur

Pour un mariage, un anniversaire ou une soirée, Pimmich tourne sur un ordinateur portable (Mac ou Windows). Le
diaporama s'affiche en plein écran sur l'écran de votre choix : le portable lui-même, une télévision ou un
vidéoprojecteur. Les invités scannent le QR code affiché et envoient leurs photos depuis leur téléphone. Chaque photo
passe aussitôt en grand avec le prénom de l'invité, puis dans le « Mur de la fête ». Les jeux de famille (menu Jeux)
fonctionnent aussi.

## Installation (une seule fois)

Récupérez Pimmich (bouton **Code > Download ZIP** sur GitHub, ou `git clone`), puis, depuis son dossier :

- **Mac** : installez [Homebrew](https://brew.sh), puis lancez `bash desktop/install_mac.sh` dans le Terminal.
  Ce script installe Python, ffmpeg et mpv, puis les bibliothèques de Pimmich.
- **Windows 10 / 11** : dans PowerShell, lancez `powershell -ExecutionPolicy Bypass -File desktop\install_windows.ps1`.
  Ce script installe Python, ffmpeg et mpv avec `winget`, puis les bibliothèques de Pimmich.
  L'édition Windows n'a pas encore été essayée en vrai : signalez tout souci.

## Lancement

Double-cliquez sur **« Pimmich événement.command »** (Mac) ou **« Pimmich evenement.bat »** (Windows). Une fenêtre
propose les réglages suivants :

| Réglage | Rôle |
|---|---|
| Nom de la fête, durée | Active le mode fête : QR code en grand, photos des invités affichées aussitôt, Mur de la fête |
| Écran du diaporama | Le portable, ou l'écran / vidéoprojecteur branché ; plein écran ou dans une fenêtre |
| Photos déposées | Dossier où arrivent les photos des invités (disque externe, dossier synchronisé...) |
| Photos préparées | Dossier des versions prêtes à afficher (peut être ailleurs que les photos déposées) |
| Port | Adresse donnée aux invités : `http://<adresse de l'ordinateur>:8080` |
| Mot de passe admin | Au premier lancement seulement (compte `admin`) |

Cliquez sur **Lancer**. Le navigateur ouvre l'administration, et le diaporama démarre sur l'écran choisi. Fermer la
fenêtre arrête tout. En ligne de commande : `python pimmich_event.py --no-gui --name "Mariage" --display 1`
(voir `--help`, et `--list-displays` pour la liste des écrans).

Au clavier, sur le diaporama :
- **→** : photo suivante ;
- **←** : photo précédente ;
- **espace** : pause ;
- **Échap** : réduire la fenêtre.

## Le réseau le jour J

Les téléphones des invités et l'ordinateur doivent être sur le **même réseau Wi-Fi**.
- Les Wi-Fi d'hôtel ou de salle isolent souvent les appareils entre eux : les invités ne joignent alors pas
  l'ordinateur. Dans ce cas, utilisez un petit routeur de voyage, ou le partage de connexion d'un téléphone.
- Au premier lancement, macOS ou Windows demandent d'autoriser Python à recevoir des connexions : acceptez.
  Sous Windows, choisissez « réseaux privés ».

## Après la fête

Les photos sont dans le dossier « Photos déposées », sous-dossier `fete_AAAAMMJJ`. Copiez-le où vous voulez : c'est
l'album de la fête. L'administration permet aussi de tout sauvegarder (`Système > Maintenance`).

## Ce qui ne s'applique pas sur un ordinateur

Les fonctions propres au Raspberry Pi sont masquées : Wi-Fi et point d'accès de secours, bouton physique, capteur
de rotation, disques à monter, mise en veille de l'écran, commande vocale, mises à jour automatiques du système.
