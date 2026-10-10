#!/bin/bash
# Fait du cadre une enceinte Spotify Connect (compte Spotify Premium) et un récepteur AirPlay
# (son de n'importe quelle application d'iPhone, d'iPad ou de Mac : Deezer, Apple Music, YouTube...).
# À lancer une fois, depuis le compte qui fait tourner Pimmich : ./utils/enable_music_receivers.sh
# (le script demande le mot de passe sudo pour installer les paquets).
set -euo pipefail
NAME="${1:-Cadre photo}"
UNIT_DIR="$HOME/.config/systemd/user"
PIMMICH_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# Identifiants Spotify du cadre (association à un compte depuis l'interface), hors du dossier de Pimmich
SPOTIFY_CACHE="$HOME/.config/pimmich/spotify-connect"
mkdir -p "$SPOTIFY_CACHE" && chmod 700 "$HOME/.config/pimmich" "$SPOTIFY_CACHE"

echo "=== Installation de librespot (Spotify Connect) et shairport-sync (AirPlay) ==="
if ! command -v librespot >/dev/null; then
    # Paquet raspotify (fournit librespot) ; son service système est désactivé au profit d'un service utilisateur
    curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
    sudo systemctl disable --now raspotify 2>/dev/null || true
fi
sudo apt-get install -y shairport-sync playerctl  # playerctl : télécommande de l'interface (MPRIS)
sudo systemctl disable --now shairport-sync 2>/dev/null || true

echo "=== Enceinte Bluetooth (A2DP) ==="
sudo apt-get install -y rfkill python3-dbus python3-gi
sudo rfkill unblock bluetooth
# Classe « Audio / haut-parleur » : les téléphones affichent le cadre comme une enceinte
if ! grep -q "^Class = 0x240414" /etc/bluetooth/main.conf; then
    sudo sed -i 's/^#\?\s*Class = .*/Class = 0x240414/' /etc/bluetooth/main.conf
    grep -q "^Class = 0x240414" /etc/bluetooth/main.conf || echo "Class = 0x240414" | sudo tee -a /etc/bluetooth/main.conf >/dev/null
fi
sudo systemctl enable bluetooth
sudo systemctl restart bluetooth
# WirePlumber : Bluetooth actif même sans session graphique ouverte
mkdir -p "$HOME/.config/wireplumber/wireplumber.conf.d"
cat > "$HOME/.config/wireplumber/wireplumber.conf.d/90-pimmich-bluetooth.conf" <<'CONF'
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
CONF
systemctl --user restart wireplumber || true

SHAIRPORT_CONF="$HOME/.config/pimmich/shairport-sync.conf"
cat > "$SHAIRPORT_CONF" <<'CONF'
// Pimmich : commandes (lecture, pause, suivant) depuis l'interface, via MPRIS sur la session
general = {
  mpris_service_bus = "Session";
  dbus_service_bus = "Session";
};
CONF

# Services utilisateur : le son passe par PipeWire, comme les vidéos et la musique du diaporama
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/pimmich-spotify.service" <<UNIT
[Unit]
Description=Pimmich - enceinte Spotify Connect
After=pipewire-pulse.service

[Service]
# --onevent : le morceau en cours (titre, artiste, pochette) est transmis au cadre pour l'affichage
ExecStart=/usr/bin/librespot --name "$NAME" --backend pulseaudio --bitrate 160 --initial-volume 70 --device-type speaker --system-cache "$SPOTIFY_CACHE" --onevent "$PIMMICH_DIR/utils/librespot_event.sh"
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
# -c : télécommande MPRIS sur la session de l'utilisateur ; -M -g : métadonnées et pochettes dans un tube, lues par pimmich-airplay-meta
ExecStart=/usr/bin/shairport-sync -c "$SHAIRPORT_CONF" -a "$NAME" -p 5100 -M -g --metadata-pipename=/tmp/shairport-sync-metadata -o pa
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
cat > "$UNIT_DIR/pimmich-bluetooth.service" <<UNIT
[Unit]
Description=Pimmich - enceinte Bluetooth
After=pipewire-pulse.service

[Service]
WorkingDirectory=$PIMMICH_DIR
# Python du système : il fournit dbus et gi
ExecStart=/usr/bin/python3 -m utils.bluetooth_receiver
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
cat > "$UNIT_DIR/pimmich-bt-mpris.service" <<UNIT
[Unit]
Description=Pimmich - télécommande des téléphones Bluetooth (MPRIS)
After=pimmich-bluetooth.service

[Service]
ExecStart=/usr/bin/mpris-proxy
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
SERVICES="pimmich-spotify.service pimmich-airplay.service pimmich-airplay-meta.service pimmich-bluetooth.service pimmich-bt-mpris.service"
systemctl --user enable $SERVICES
systemctl --user restart $SERVICES  # nouvelles options prises en compte
sudo loginctl enable-linger "$USER"  # les services démarrent avec le cadre, même sans session ouverte
echo "✅ « $NAME » est disponible comme enceinte dans Spotify (Premium), en AirPlay et en Bluetooth."
