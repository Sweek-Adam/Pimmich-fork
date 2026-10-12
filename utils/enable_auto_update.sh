#!/bin/bash
# Active (ou coupe) la mise à jour automatique quotidienne de Pimmich dans la crontab de l'utilisateur.
# À lancer sans sudo, depuis le compte qui fait tourner Pimmich :
#   ~/pimmich/utils/enable_auto_update.sh                  Pimmich chaque jour à 04:30
#   ~/pimmich/utils/enable_auto_update.sh --system         Pimmich + paquets du système (demande le mot de passe une fois)
#   ~/pimmich/utils/enable_auto_update.sh --time 03:15     autre heure
#   ~/pimmich/utils/enable_auto_update.sh --off            coupe la mise à jour automatique
# Journal : ~/pimmich/logs/auto_update.log

set -e
SCRIPT="$(cd "$(dirname "$0")" && pwd)/auto_update.sh"
TIME="04:30"
SYSTEM=""
OFF=0
while [ $# -gt 0 ]; do
    case "$1" in
        --system) SYSTEM=" --system" ;;
        --time) TIME="$2"; shift ;;
        --off) OFF=1 ;;
        *) echo "Option inconnue : $1"; exit 1 ;;
    esac
    shift
done
if ! [[ "$TIME" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
    echo "Heure invalide : $TIME (format HH:MM)"; exit 1
fi
if [ "$(id -u)" = 0 ]; then
    echo "À lancer sans sudo, depuis le compte qui fait tourner Pimmich."; exit 1
fi
chmod +x "$SCRIPT"

# Crontab : on retire l'ancienne ligne, puis on ajoute la nouvelle
CURRENT=$(crontab -l 2> /dev/null | grep -v "auto_update.sh" || true)
if [ "$OFF" = 1 ]; then
    printf '%s\n' "$CURRENT" | sed '/^$/d' | crontab -
    echo "✅ Mise à jour automatique coupée."
    exit 0
fi
HOUR=$((10#${TIME%:*}))
MINUTE=$((10#${TIME#*:}))
LINE="$MINUTE $HOUR * * * $SCRIPT$SYSTEM"
printf '%s\n%s\n' "$CURRENT" "$LINE" | sed '/^$/d' | crontab -

if [ -n "$SYSTEM" ]; then
    # apt-get sans mot de passe pour ce compte (avec DEBIAN_FRONTEND), vérifié avant d'être installé
    RULE="$USER ALL=(root) NOPASSWD:SETENV: /usr/bin/apt-get"
    TMP=$(mktemp)
    echo "$RULE" > "$TMP"
    sudo visudo -cf "$TMP" > /dev/null
    sudo install -m 440 -o root -g root "$TMP" /etc/sudoers.d/pimmich-apt
    rm -f "$TMP"
fi

echo "✅ Mise à jour automatique chaque jour à $TIME${SYSTEM:+ (Pimmich et système)}."
echo "   Ligne de la crontab : $LINE"
echo "   Journal : $(dirname "$SCRIPT")/../logs/auto_update.log"
