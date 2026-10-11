#!/bin/bash
# Repasse du bureau Raspberry Pi OS au mode cadre photo Pimmich (inverse de « Repasser sur le bureau ») :
# démarrage en console avec connexion automatique, lancement de Sway (qui lance Pimmich), puis redémarrage.
# Lancé par le raccourci « Revenir au cadre Pimmich » du bureau ; `--yes` : sans demander de confirmation.

TITLE="Pimmich"
QUESTION="Revenir au cadre photo Pimmich ?\n\nLe Raspberry Pi va redémarrer et le bureau ne s'affichera plus."

ask() {
    [ "$1" = "--yes" ] && return 0
    if command -v zenity > /dev/null; then
        zenity --question --title="$TITLE" --text="$QUESTION" --width=360 2> /dev/null
    else
        read -r -p "Revenir au cadre photo Pimmich (le Raspberry Pi va redémarrer) ? [o/N] " answer
        [[ "$answer" =~ ^[oOyY] ]]
    fi
}

fail() {
    if command -v zenity > /dev/null; then
        zenity --error --title="$TITLE" --text="$1" --width=360 2> /dev/null
    fi
    echo "❌ $1" >&2
    exit 1
}

ask "$1" || exit 0

# 1. Lancement automatique de Sway sur la console tty1 (comme setup.sh, étape 10)
PROFILE="$HOME/.bash_profile"
if ! grep -q 'exec sway' "$PROFILE" 2> /dev/null; then
    # copie puis remplacement : fonctionne même si le fichier appartient à root (créé par « sudo ./setup.sh »)
    TMP="$PROFILE.pimmich-tmp"
    { cat "$PROFILE" 2> /dev/null
      echo 'if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then'
      echo '  exec sway'
      echo 'fi'
    } > "$TMP" && mv -f "$TMP" "$PROFILE" || fail "Impossible de modifier $PROFILE."
fi

# 2. Démarrage en console avec connexion automatique (setup.sh, étape 9)
sudo -n raspi-config nonint do_boot_behaviour B2 || fail "Impossible de changer le mode de démarrage (raspi-config)."

# 3. Redémarrage
sudo -n reboot || fail "Impossible de redémarrer : redémarrez le Raspberry Pi vous-même."
