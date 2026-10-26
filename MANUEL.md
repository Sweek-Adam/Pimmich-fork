# 📘 Manuel du cadre photo

Ce manuel explique, pas à pas, comment se servir du cadre au quotidien. Il s'adresse à toute la famille : pas besoin
d'être informaticien. Pour installer le cadre, voir [INSTALL.md](INSTALL.md) ; pour les questions précises, la
[FAQ](FAQ.md).

*English version: [MANUAL_en.md](MANUAL_en.md).*

---

## 📖 Sommaire

1. [Ouvrir l'interface du cadre](#1-ouvrir-linterface-du-cadre)
2. [Ajouter des photos](#2-ajouter-des-photos)
3. [Retrouver et ranger ses photos](#3-retrouver-et-ranger-ses-photos)
4. [Ce que montre l'écran](#4-ce-que-montre-lécran)
5. [Piloter le cadre sans téléphone](#5-piloter-le-cadre-sans-téléphone)
6. [Invités, fêtes et jeux](#6-invités-fêtes-et-jeux)
7. [Rester proches : messages, cœurs, cadres jumelés](#7-rester-proches--messages-cœurs-cadres-jumelés)
8. [Créer des souvenirs : livre, calendrier, film](#8-créer-des-souvenirs--livre-calendrier-film)
9. [Les e-mails du cadre](#9-les-e-mails-du-cadre)
10. [Entretien, sauvegardes et notifications](#10-entretien-sauvegardes-et-notifications)
11. [Le cadre allume, éteint, redémarre](#11-le-cadre-allume-éteint-redémarre)
12. [Vie privée : ce qui sort de la maison](#12-vie-privée--ce-qui-sort-de-la-maison)

---

## 1. Ouvrir l'interface du cadre

Sur un téléphone ou un ordinateur relié au **Wi-Fi de la maison**, ouvrez le navigateur et tapez :

- **`cadre-photo.local`** (ou `cadre-photo.home` sur une Livebox), ou l'adresse IP du cadre ;
- depuis l'extérieur, l'adresse **Tailscale** du cadre si elle a été installée.

La première fois, le navigateur signale un certificat « non sûr » : c'est normal (le certificat est fabriqué par le
cadre lui-même), acceptez-le. Connectez-vous avec votre compte. Chaque membre de la famille peut avoir le sien
(**Système › Comptes**).

Le menu regroupe les pages en six rubriques : **Accueil**, **Photos**, **Écran**, **Partage**, **Jeux**, **Système**.
La page **Accueil › Nouveautés** présente les dernières fonctions.

> 💡 Ajoutez l'interface à l'écran d'accueil du téléphone (menu Partager › « Sur l'écran d'accueil ») : elle s'ouvre
> alors comme une application.

## 2. Ajouter des photos

### Depuis le téléphone
- **Photos › Importer** : choisissez des photos et des vidéos sur le téléphone, elles partent sur le cadre.
- Les **invités** (sans compte) utilisent la page invités : QR code affiché sur le cadre, ou lien `…/upload`. Leurs
  photos attendent votre validation dans **Partage › À valider** (sauf pendant une fête, ou pour les invités de
  confiance).
- Également : **Telegram**, **e-mail** (le cadre relève sa propre boîte mail), **WhatsApp** et le partage direct
  depuis Android.

### Depuis vos bibliothèques en ligne
**Photos › Sources** : Google Drive, Immich, Dropbox, OneDrive, iCloud (albums partagés), partage réseau (NAS), clé USB.
Le cadre se synchronise tout seul ; la petite pastille « Préparation en cours » n'apparaît que s'il y a des nouveautés.

### Les vieilles photos papier : le scanner
**Photos › Importer › Scanner une photo papier**

1. Posez le tirage sur une **table sombre**, bien éclairé, sans reflet.
2. Touchez « Photographier un tirage » et prenez la photo avec le téléphone.
3. Le cadre trouve les bords, **redresse** la photo et **ravive** les couleurs passées. Tournez-la si besoin.
4. « Ajouter au cadre » : elle rejoint la source « Photos papier scannées ».

### Colorier les photos noir et blanc
**Photos › Importer › Colorisation des photos noir et blanc**

- La première fois, touchez **« Installer la colorisation »** (129 Mo, téléchargés une seule fois).
- Ensuite, dans la **Bibliothèque**, ouvrez une photo noir et blanc (ou sépia) et touchez **« Coloriser »** : une
  copie en couleur rejoint le diaporama (source « Photos colorisées »). L'original n'est jamais modifié.
- En option, les tirages noir et blanc **scannés** sont colorisés d'office (l'original est gardé à part).

Les couleurs sont douces et plausibles, calculées sur le cadre (rien ne part sur internet).

### Préparation des médias
Chaque photo est « préparée » à la taille de l'écran ; les vidéos sont réencodées (les grosses, la nuit).
**Photos › Préparation des médias** montre l'état de chaque média :
- **À préparer** : bouton « Préparer » pour rattraper un média resté de côté ;
- **En échec** (fichier abîmé, illisible) : la corbeille 🗑 le supprime, ou « Supprimer les N en échec » pour toute
  une source.

## 3. Retrouver et ranger ses photos

**Photos › Bibliothèque** : toutes les photos, avec une recherche par texte (lieu, légende, nom), date, source,
personne (avec Immich), et « par contenu » (« plage », « chien »… avec Immich).

En ouvrant une photo, on peut :
- écrire une **légende** (et choisir son style), la mettre en **favori** ⭐ ;
- **« Raconter cette photo »** 🎤 : enregistrer l'histoire de la photo de vive voix (90 s au plus). Le cadre lit ce
  **souvenir vocal** quand la photo passe à l'écran ;
- voir les **commentaires** laissés par les invités (et les supprimer) ;
- **« Coloriser »** une photo noir et blanc ;
- adopter une **légende proposée** ✨ (voir ci-dessous).

### Légendes proposées automatiquement
**Écran › Légendes › Légendes proposées automatiquement** : chaque nuit, le cadre propose une courte description et
des mots-clés (plage, neige, anniversaire…). Ils servent à la recherche, et un clic suffit pour les adopter. Deux
façons :
- **Immich** : des mots-clés, gratuitement (photos venues d'Immich) ;
- **Claude** : une vraie phrase pour chaque photo. Une copie réduite de la photo est envoyée à Anthropic (environ
  0,7 centime par photo, sur votre compte Anthropic). **Désactivé par défaut.**

Une légende écrite à la main n'est jamais remplacée.

### Playlists, favoris, carte
- **Playlists** : une sélection de photos à passer en boucle (avec musique si vous voulez).
- **Favoris** : vos photos préférées, qui passent plus souvent.
- **Carte** : les photos sur une carte du monde, regroupées par voyage.

## 4. Ce que montre l'écran

### Le diaporama
**Écran › Affichage** règle l'essentiel : heures d'allumage (semaine, week-end), durée de chaque photo, transitions,
sources montrées.

- **Effet Pan/Zoom** : la photo bouge doucement pendant qu'elle est affichée. Le mouvement **Ken Burns** zoome
  lentement vers les **visages** (le mouvement « glissement » va d'un bord à l'autre).
- **Photos oubliées** : celles qui ne sont jamais (ou rarement) passées reviennent plus souvent.
- **Longues vidéos** : le cadre n'en montre que le **passage le plus animé** (20 s par défaut) ; la vidéo complète
  reste dans la bibliothèque.
- **Améliorer automatiquement les photos sombres ou ternes** (**Écran › Dispositions**) : légère retouche de la copie
  affichée, jamais de l'original ; les ambiances de soirée colorées restent telles quelles.

### Les diapositives spéciales
- **Ce jour-là** : les photos prises un jour comme aujourd'hui, les années précédentes.
- **Cette semaine** : l'agenda familial et les comptes à rebours.
- **Votre semaine sur le cadre** : le dimanche soir, les nouvelles photos de la semaine, qui les a envoyées, les
  messages et les cœurs.
- **Dispositions** (Écran › Dispositions) : mosaïques, murs, cartes postales, thèmes de saison et d'anniversaire.

### Horloge, météo, nuit
**Écran › Horloge & météo** : horloge, météo animée, agenda. Le soir, la luminosité baisse ; la nuit, une horloge
discrète peut remplacer l'écran noir.

### L'écran de démarrage
À l'allumage, le cadre affiche « Votre cadre photo s'allume » dans l'un de quatre styles (tiré au hasard), avec ses
fonctions et le QR code d'envoi, puis passe à la première photo sans écran noir.

### Diffuser sur une télé (Chromecast)
**Écran › Affichage › Diffuser sur une télé** : « Chercher les télés », choisissez la télé, puis **« Diffuser le
diaporama »** ou **« Diffuser le film »** (le film de l'année, une fois « passé sur le cadre »). « Arrêter » rend la
télé à son écran d'accueil.

## 5. Piloter le cadre sans téléphone

### La télécommande de la télé (HDMI-CEC)
Si le cadre est branché sur une télé (avec le HDMI-CEC activé dans les réglages de la télé : Anynet+, Bravia Sync,
SimpLink…) et que la télé est sur l'entrée du cadre :

| Touche | Action |
|---|---|
| ▶ / ◀ (ou chaîne + / −) | photo suivante / précédente |
| OK, lecture, pause | pause / reprise |
| ▲ ou touche **rouge** | ❤️ sur la photo affichée |
| touche **bleue** | « je pense à vous » vers les autres cadres de la famille |
| Stop, Retour | mise en veille du cadre |
| n'importe quelle touche (cadre en veille) | réveil |

Réglage : **Écran › Affichage › Télévision**.

### Le détecteur de mouvement
Un petit capteur infrarouge (HC-SR501, quelques euros) branché sur le Raspberry Pi : l'écran **s'éteint** quand
personne n'est passé devant le cadre depuis quelques minutes, et **se rallume** dès que quelqu'un entre dans la pièce.
Câblage et réglage : **Écran › Affichage › Détecteur de mouvement** (la carte indique le dernier mouvement vu, pratique
pour vérifier le câblage).

### Le bouton physique
Un bouton branché sur le Raspberry Pi : un appui met le cadre en veille, un autre le réveille
(**Écran › Affichage › Bouton physique**).

### Le mode grands-parents
**Partage › Invités › Mode grands-parents** : une page **toute simple, à très gros boutons**, pour le téléphone d'une
personne qui n'aime pas les applications :

1. Écrivez le prénom (« Bonjour Mamie ! ») et touchez « Créer le lien ».
2. Scannez le **QR code** avec son téléphone (sur le Wi-Fi de la maison), puis ajoutez la page à l'écran d'accueil.
3. Elle voit la photo affichée et peut : passer à la suivante, mettre en pause, envoyer un ❤️, **écrire un mot** ou
   **le dire à voix haute**, envoyer « je pense à vous » aux autres cadres, allumer ou éteindre le cadre.

Pas de mot de passe ; la page ne marche que sur le Wi-Fi de la maison. « Changer le lien » rend l'ancien inutilisable.

## 6. Invités, fêtes et jeux

### La page invités
Le QR code affiché dans un coin du cadre mène à la page invités : envoyer des **photos**, un **message**, un
**dessin**, un **message vocal**, signer le **livre d'or**, et, sur la photo affichée en ce moment, envoyer une
**réaction** (❤️ 😂 😮 👏) ou un **petit mot** 💬 qui s'affiche aussitôt en bandeau sur le cadre.

### Le mode fête
**Partage › Invités › Mode fête** : nom de la fête, durée, puis « Lancer ». Un grand QR code reste à l'écran ; les
photos des invités s'affichent **tout de suite**, en grand, avec leur prénom, puis dans le « Mur de la fête ». À la fin,
le diaporama habituel reprend et l'album de la fête reste dans les sources.

- **QR code du Wi-Fi** : cochez « Afficher aussi le QR code du Wi-Fi de la maison » : les invités se connectent d'un
  scan (le mot de passe est lu dans le Raspberry Pi au moment de l'afficher, jamais enregistré).
- **Photomaton** : voir ci-dessous.

### Le photomaton
**Partage › Invités › Photomaton** : pendant une fête, les invités **impriment** la photo affichée sur le cadre, sur
une imprimante Wi-Fi de la maison.

1. « Chercher les imprimantes », puis touchez la vôtre.
2. Choisissez le **papier** : photo 10 × 15, ou A4 (photo en grand).
3. « Tirage d'essai » pour vérifier.
4. Cochez « Ouvrir le photomaton pendant les fêtes » et le nombre de **tirages par invité**. En option, chaque photo
   reçue peut être imprimée d'elle-même (avec un plafond pour la fête).

Chaque tirage porte une marge blanche, le nom de la fête et la date, comme un vrai photomaton. Les invités ont un
bouton « 🖨️ Imprimer la photo à l'écran » sur leur page.

### Le mur de cadres
**Partage › Invités › Mur de cadres** : posez plusieurs cadres côte à côte ; ils affichent **ensemble une même grande
photo**, découpée entre les écrans et changée au même instant sur tous. Choisissez les cadres et leur ordre de gauche à
droite, l'espace entre les écrans (bordures), la durée de chaque photo, puis « Lancer le mur ». Les autres cadres
doivent être ajoutés dans « Cadres de la famille » (voir § 7).

### Les jeux
**Jeux › Jeux de famille** : onze jeux joués depuis les téléphones (« Où et quand ? », « Qui est-ce ? », bingo,
ligne du temps…). Le cadre affiche la partie et les règles à côté du QR code.

## 7. Rester proches : messages, cœurs, cadres jumelés

### Les messages
**Photos › Messages** : un mot affiché en grand sur le cadre, avec un style. Il peut être **programmé** (le jour d'un
anniversaire) ou **récurrent** (chaque lundi…). Les invités peuvent aussi en envoyer depuis la page invités.

### Les cadres de la famille
**Partage › Invités › Cadres de la famille** : pilotez d'ici les autres cadres (chez Mamie, au chalet…) : voir leur
photo affichée, les allumer, leur envoyer des photos ou un message.

1. Sur l'autre cadre : « Code d'association » › « Créer un code ».
2. Ici : son adresse (Tailscale ou réseau local) et ce code.

Ensuite, pour chaque cadre :
- **💞 « Je pense à vous »** : des cœurs s'envolent sur son écran, avec « Mamie pense à vous » ;
- **partage automatique** (cases à cocher, désactivé par défaut) : les nouvelles photos reçues et les messages
  écrits ici partent aussi sur ce cadre. Seules les nouveautés partent ; ce qui vient de l'autre cadre ne revient
  jamais (pas de boucle) ; les photos de Google Drive ou d'Immich ne sont pas recopiées.

## 8. Créer des souvenirs : livre, calendrier, film

Tout se trouve en bas de **Photos › Bibliothèque**.

### Le livre photo de l'année
Choisissez l'année, « Créer le livre » : un **PDF prêt à imprimer** (A4 à l'italienne) avec une couverture, les plus
belles photos mois par mois (les plus aimées et les favorites d'abord, sans les photos floues ni les captures
d'écran), puis « l'année en chiffres ». Quelques minutes sur un Raspberry Pi ; puis « Télécharger ».

### Le calendrier photo
« Créer le calendrier » (l'année suivante, par défaut) : un mois par page, en **A4 portrait**, avec une belle photo
prise ce mois-là une année précédente et la grille des jours où figurent les **anniversaires de la famille**, la fête
des mères et des pères.

### Le film de l'année
Choisissez une musique, « Monter le film » : un petit film des plus belles photos, avec titre, mois, fondus et musique
(une dizaine de minutes de montage). Ensuite : « Regarder », « Télécharger », ou **« Passer sur le cadre »** (il
rejoint le diaporama, et peut être diffusé sur une télé Chromecast).

## 9. Les e-mails du cadre

Le cadre envoie ses e-mails depuis **sa propre boîte mail**, la même que pour recevoir des photos (**Photos ›
Sources › Photos reçues par e-mail**). Les destinataires ne voient pas les adresses des autres.

- **Photo du jour** (**Partage › Invités**) : pour les proches qui n'ont pas de cadre, une photo par jour à l'heure
  choisie (un souvenir « ce jour-là » de préférence). Jamais la même photo avant deux mois.
- **Bilan du mois** (**Partage › Invités**) : le 1er du mois, les photos reçues et de qui, les affichages, les cœurs
  et les photos les plus aimées.

Les deux sont **désactivés par défaut** ; « Envoyer maintenant » permet d'essayer.

## 10. Entretien, sauvegardes et notifications

### Notifications (Système › Notifications)
Sur le téléphone (application ntfy) : photos d'invités, erreurs de synchronisation, problèmes du cadre, imports
terminés, bilan du jour… et les **anniversaires à venir** (trois jours avant, pour préparer un mot ou un message
vocal, puis le jour J).

### Sauvegardes (Système › Maintenance)
- **Sauvegarde complète** : réglages, comptes, messages, playlists… à télécharger, ou **avec les photos** sur un
  disque USB ou un NAS.
- **Automatiquement chaque semaine** : cochez la case, choisissez le support, le jour et le nombre de sauvegardes à
  garder. Elle se fait la nuit ; la place libre est vérifiée avant ; une notification prévient en cas d'échec.
- **Restaurer** : un clic sur une sauvegarde.

### Mises à jour
**Système › Maintenance** : mise à jour en un clic (avec retour arrière si quelque chose se passe mal).

## 11. Le cadre allume, éteint, redémarre

- Le cadre s'allume et s'éteint seul selon les heures choisies (**Écran › Affichage**).
- L'**accueil** de l'interface permet de le mettre en veille, de le réveiller, de passer une photo.
- Le travail lourd (grosses vidéos, légendes automatiques, sauvegarde de la semaine) se fait **la nuit**, écran
  éteint.

## 12. Vie privée : ce qui sort de la maison

Par défaut, **rien ne sort de la maison** en dehors des synchronisations que vous configurez (Google Drive, Immich…).
Ces fonctions envoient des données à l'extérieur et sont **toutes désactivées par défaut** :

| Fonction | Ce qui sort | Où |
|---|---|---|
| Invités hors de la maison (Tailscale Funnel) | la page invités devient joignable par lien secret | internet |
| Photo du jour, bilan du mois | une ou quelques photos | les adresses e-mail choisies |
| Partage automatique entre cadres | nouvelles photos et messages | les cadres de la famille choisis |
| Légendes proposées par Claude | une copie réduite de chaque photo | Anthropic |
| Notifications | de courts textes | le service ntfy |

La colorisation, le scanner, le livre photo, le film et la reconnaissance des visages se font **sur le cadre**.
