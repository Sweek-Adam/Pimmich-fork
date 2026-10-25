#!/bin/bash
# Droits sudo de Pimmich : seulement les commandes dont le cadre a besoin, sans mot de passe.
#   sudo ~/pimmich/utils/harden_sudo.sh           écrit et vérifie la liste (/etc/sudoers.d/pimmich-auth)
#   sudo ~/pimmich/utils/harden_sudo.sh --apply   et retire en plus le « tout sans mot de passe » de Raspberry Pi Imager
#   sudo ~/pimmich/utils/harden_sudo.sh --undo    remet le « tout sans mot de passe »
# Après --apply, les autres commandes sudo demandent le mot de passe du compte (celui choisi dans Imager).
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo "À lancer avec sudo : sudo $0 $*"; exit 1; fi

USER_NAME="${SUDO_USER:-$(logname 2> /dev/null || echo adam)}"
HOME_DIR=$(getent passwd "$USER_NAME" | cut -d: -f6)
RULES=/etc/sudoers.d/pimmich-auth
FULL=/etc/sudoers.d/90-cloud-init-users
BACKUP="$HOME_DIR/.pimmich-sudoers-imager.bak"
CREDENTIALS=/boot/firmware/credentials.json

if [ "${1:-}" = "--undo" ]; then
    if [ -f "$BACKUP" ]; then
        install -m 440 "$BACKUP" "$FULL" && visudo -c > /dev/null && echo "✅ « Tout sans mot de passe » rétabli."
    else
        echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" > "$FULL" && chmod 440 "$FULL" && echo "✅ « Tout sans mot de passe » rétabli."
    fi
    exit 0
fi

COMMANDS="/usr/bin/tee $CREDENTIALS, /usr/bin/tee /sys/class/drm/card*-HDMI-A-*/status, /usr/sbin/reboot, /usr/sbin/shutdown, \\
/usr/bin/nmcli, /usr/bin/raspi-config, /usr/bin/mount, /usr/bin/umount, /usr/bin/timedatectl, \\
/usr/bin/mkdir -p /mnt/pimmich/*, /usr/bin/chown [0-9]*\\:[0-9]* /mnt/pimmich/*"
TMP=$(mktemp)
{
    echo "# Pimmich : commandes autorisées sans mot de passe (utils/harden_sudo.sh)"
    echo "$USER_NAME ALL=(root) NOPASSWD: $COMMANDS"
    echo "$USER_NAME ALL=(root) NOPASSWD:SETENV: /usr/bin/apt-get"
} > "$TMP"
if ! visudo -cf "$TMP" > /dev/null; then
    echo "❌ Liste refusée par visudo : rien n'est changé."; rm -f "$TMP"; exit 1
fi
install -m 440 "$TMP" "$RULES"
rm -f "$TMP" /etc/sudoers.d/pimmich-apt  # apt-get : maintenant dans la même liste
echo "✅ Liste des commandes de Pimmich écrite ($RULES)."

if [ "${1:-}" = "--apply" ] && [ -f "$FULL" ]; then
    # Vérifier, comme le compte de Pimmich, que chaque commande reste permise sans le « tout autoriser »
    cp "$FULL" "$BACKUP" && chown "$USER_NAME" "$BACKUP" && chmod 600 "$BACKUP"
    mv "$FULL" "$FULL.off"
    missing=0
    for cmd in "/usr/bin/nmcli -v" "/usr/bin/timedatectl status" "/usr/bin/raspi-config nonint get_boot_cli" "/usr/bin/apt-get -v"; do
        if ! sudo -u "$USER_NAME" sudo -n $cmd > /dev/null 2>&1; then echo "❌ Refusé : $cmd"; missing=1; fi
    done
    if [ "$missing" = 1 ]; then
        mv "$FULL.off" "$FULL"; echo "❌ Retour au « tout sans mot de passe » (rien n'a changé)."; exit 1
    fi
    rm -f "$FULL.off"
    echo "✅ « Tout sans mot de passe » retiré (copie : $BACKUP). Pour revenir en arrière : sudo $0 --undo"
fi
