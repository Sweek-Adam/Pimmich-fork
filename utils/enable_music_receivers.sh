#!/bin/bash
# Fait du cadre une enceinte Spotify Connect (compte Spotify Premium) et un récepteur AirPlay
# (son de n'importe quelle application d'iPhone, d'iPad ou de Mac : Deezer, Apple Music, YouTube...).
# À lancer une fois, depuis le compte qui fait tourner Pimmich : ./utils/enable_music_receivers.sh
# (le script demande le mot de passe sudo pour installer les paquets).
set -euo pipefail
NAME="${1:-Cadre photo}"
UNIT_DIR="$HOME/.config/systemd/user"
PIMMICH_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Installation de librespot (Spotify Connect) et shairport-sync (AirPlay) ==="
if ! command -v librespot >/dev/null; then
    # Paquet raspotify (fournit librespot) ; son service système est désactivé au profit d'un service utilisateur
    curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
    sudo systemctl disable --now raspotify 2>/dev/null || true
fi
sudo apt-get install -y shairport-sync
sudo systemctl disable --now shairport-sync 2>/dev/null || true

# Services utilisateur : le son passe par PipeWire, comme les vidéos et la musique du diaporama
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/pimmich-spotify.service" <<UNIT
[Unit]
Description=Pimmich - enceinte Spotify Connect
After=pipewire-pulse.service

[Service]
# --onevent : le morceau en cours (titre, artiste, pochette) est transmis au cadre pour l'affichage
ExecStart=/usr/bin/librespot --name "$NAME" --backend pulseaudio --bitrate 160 --initial-volume 70 --device-type speaker --onevent "$PIMMICH_DIR/utils/librespot_event.sh"
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
cat > "$UNIT_DIR/pimmich-airplay.service" <<UNIT
[Unit]
Description=Pimmich - récepteur AirPlay
After=pipewire-pulse.service

[Service]
# Port 5100 : le port par défaut d'AirPlay (5000) est celui de Pimmich
# -M -g : métadonnées et pochettes dans un tube, lues par pimmich-airplay-meta
ExecStart=/usr/bin/shairport-sync -a "$NAME" -p 5100 -M -g --metadata-pipename=/tmp/shairport-sync-metadata -o pa
Restart=on-failure

[Install]
WantedBy=default.target
UNIT
cat > "$UNIT_DIR/pimmich-airplay-meta.service" <<UNIT
[Unit]
Description=Pimmich - morceau en cours (AirPlay)
After=pimmich-airplay.service

[Service]
WorkingDirectory=$PIMMICH_DIR
ExecStart=$PIMMICH_DIR/venv/bin/python -m utils.now_playing airplay
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable pimmich-spotify.service pimmich-airplay.service pimmich-airplay-meta.service
systemctl --user restart pimmich-spotify.service pimmich-airplay.service pimmich-airplay-meta.service  # nouvelles options prises en compte
sudo loginctl enable-linger "$USER"  # les services démarrent avec le cadre, même sans session ouverte
echo "✅ « $NAME » est disponible comme enceinte dans Spotify (Premium) et en AirPlay."
