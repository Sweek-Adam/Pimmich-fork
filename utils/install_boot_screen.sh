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

CACHE="$PIMMICH/cache/boot_screen"
QUIT_DROPIN=/etc/systemd/system/plymouth-quit.service.d/pimmich-retain.conf
SWAY_CONFIG="$HOME_DIR/.config/sway/config"

if [ "${1:-}" = "--undo" ]; then
    rm -f "$QUIT_DROPIN" && systemctl daemon-reload
    [ -f "$SWAY_CONFIG" ] && sed -i '/# Pimmich : écran de démarrage/,+1d' "$SWAY_CONFIG"
    rm -f "$CACHE/pick.png"
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
# Mêmes fonds pour le cadre (sway, puis diaporama jusqu'à la première photo), et style du prochain démarrage
sudo -u "$USER_NAME" mkdir -p "$CACHE"
sudo -u "$USER_NAME" cp "$TMP"/bg*.png "$CACHE"/
rm -rf "$TMP"
if [ ! -f "$CACHE/pick.png" ]; then
    sudo -u "$USER_NAME" "$PIMMICH/venv/bin/python" -c "from PIL import Image; import random; Image.new('L', (random.randint(1, 4), 1)).save('$CACHE/pick.png')"
fi
sudo -u "$USER_NAME" bash -c "cd '$PIMMICH' && venv/bin/python -m utils.boot_screen --after-boot"
ln -sf "$CACHE/pick.png" "$DEST/pick.png"

# Fin de l'écran de démarrage : l'image reste figée (pas d'écran noir ni de texte) jusqu'à l'affichage du cadre
install -d "$(dirname "$QUIT_DROPIN")"
printf '[Service]\nExecStart=\nExecStart=-/usr/bin/plymouth quit --retain-splash\n' > "$QUIT_DROPIN"
systemctl daemon-reload
sudo -u "$USER_NAME" touch "$HOME_DIR/.hushlogin"
for getty in /etc/systemd/system/getty@tty1.service.d/*.conf; do
    [ -f "$getty" ] && grep -q -- "--autologin" "$getty" && ! grep -q -- "--noissue" "$getty" && sed -i 's/--autologin/--noissue --autologin/' "$getty"
done
if [ -f "$SWAY_CONFIG" ] && ! grep -q "# Pimmich : écran de démarrage" "$SWAY_CONFIG"; then
    printf '# Pimmich : écran de démarrage (même image jusqu au diaporama)\noutput * bg %s fill\n' "$CACHE/current.png" >> "$SWAY_CONFIG"
fi

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
