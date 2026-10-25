#!/bin/bash
# Écran de démarrage du cadre photo (à la place de celui de Raspberry Pi OS, sans messages du système).
# Quatre styles, un tiré au hasard à chaque démarrage. Le QR code mène à http://<nom du cadre>.local/upload.
#   sudo ~/pimmich/utils/install_boot_screen.sh          dessine et installe le thème « cadre-photo »
#   sudo ~/pimmich/utils/install_boot_screen.sh --undo   remet l'écran de Raspberry Pi OS (pix)
# À relancer si le nom du cadre change (le QR code contient l'adresse).
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo "À lancer avec sudo : sudo $0 $*"; exit 1; fi

USER_NAME="${SUDO_USER:-$(logname 2> /dev/null || echo adam)}"
HOME_DIR=$(getent passwd "$USER_NAME" | cut -d: -f6)
PIMMICH="$HOME_DIR/pimmich"
THEME=cadre-photo
DEST="/usr/share/plymouth/themes/$THEME"

if [ "${1:-}" = "--undo" ]; then
    plymouth-set-default-theme -R pix && echo "✅ Écran de démarrage de Raspberry Pi OS remis."
    exit 0
fi

# Taille de l'écran (sinon 1920x1080 : le thème s'adapte de toute façon à l'écran)
SIZE=$(tr ',' 'x' < /sys/class/graphics/fb0/virtual_size 2> /dev/null || true)
case "$SIZE" in [0-9]*x[0-9]*) ;; *) SIZE=1920x1080 ;; esac

TMP=$(mktemp -d)
chown "$USER_NAME" "$TMP"
echo "🎨 Dessin des 4 styles ($SIZE), une minute environ…"
sudo -u "$USER_NAME" bash -c "cd '$PIMMICH' && '$PIMMICH/venv/bin/python' -m utils.boot_screen '$TMP' '$SIZE'" > /dev/null
rm -rf "$DEST"
install -d "$DEST"
install -m 644 "$TMP"/* "$DEST"/
rm -rf "$TMP"

# Ni logo ni texte du noyau, curseur caché, écran Plymouth dès le début
CMDLINE=/boot/firmware/cmdline.txt
for option in quiet splash logo.nologo vt.global_cursor_default=0 plymouth.ignore-serial-consoles loglevel=3; do
    grep -qw -- "$option" "$CMDLINE" || sed -i "1 s/\$/ $option/" "$CMDLINE"
done
CONFIG=/boot/firmware/config.txt
grep -q '^disable_splash=1' "$CONFIG" || echo "disable_splash=1" >> "$CONFIG"

echo "📦 Installation du thème (mise à jour de l'initramfs)…"
plymouth-set-default-theme -R "$THEME"
echo "✅ Écran de démarrage installé : il apparaîtra au prochain redémarrage."
