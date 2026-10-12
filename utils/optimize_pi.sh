#!/bin/bash
# Optimise Raspberry Pi OS pour le cadre photo : démarrage plus rapide, moins de processus en tâche de fond,
# moins d'écritures sur la carte SD. Rien d'utile au cadre, au bureau ou à l'enceinte Bluetooth n'est touché.
#   sudo ~/pimmich/utils/optimize_pi.sh            applique les optimisations
#   sudo ~/pimmich/utils/optimize_pi.sh --dry-run  montre ce qui serait fait, sans rien changer
#   sudo ~/pimmich/utils/optimize_pi.sh --undo     revient à la configuration d'origine
# Un redémarrage est nécessaire ensuite (sudo reboot).

MODE="apply"
case "$1" in
    --dry-run) MODE="dry" ;;
    --undo) MODE="undo" ;;
    "") ;;
    *) echo "Option inconnue : $1"; exit 1 ;;
esac
if [ "$MODE" != "dry" ] && [ "$(id -u)" != 0 ]; then
    echo "À lancer avec sudo : sudo $0 $*"; exit 1
fi

CONFIG=/boot/firmware/config.txt
BACKUP=/boot/firmware/config.txt.pimmich-orig
SYSCTL=/etc/sysctl.d/90-pimmich.conf
CLOUD_OFF=/etc/cloud/cloud-init.disabled
# Services inutiles pour un cadre photo : mises à jour automatiques du système (remplacées par
# utils/auto_update.sh à 4 h 30, pour éviter qu'elles se gênent), index des pages de manuel, attente du réseau
# au démarrage (Pimmich réessaie tout seul), partages NFS (Pimmich utilise Samba) et impression.
UNITS="apt-daily.timer apt-daily-upgrade.timer man-db.timer NetworkManager-wait-online.service
       rpcbind.service rpcbind.socket nfs-blkmap.service cups.service cups.socket cups.path cups-browsed.service"

say() { echo "$*"; }
run() {
    if [ "$MODE" = "dry" ]; then echo "   (aperçu) $*"; else "$@" > /dev/null 2>&1; fi
}
exists() { systemctl cat "$1" > /dev/null 2>&1; }

if [ "$MODE" = "undo" ]; then
    say "=== Retour à la configuration d'origine ==="
    for unit in $UNITS; do
        exists "$unit" && systemctl enable "$unit" > /dev/null 2>&1 && say "✅ $unit réactivé"
    done
    rm -f "$CLOUD_OFF" && say "✅ cloud-init réactivé"
    rm -f "$SYSCTL" && sysctl --system > /dev/null && say "✅ Réglages d'écriture disque d'origine"
    if [ -f "$BACKUP" ]; then
        cp "$BACKUP" "$CONFIG" && say "✅ $CONFIG restauré"
    fi
    say "Redémarrez pour terminer : sudo reboot"
    exit 0
fi

say "=== Optimisation du Raspberry Pi pour le cadre photo ==="

# 1. Services et tâches planifiées inutiles
for unit in $UNITS; do
    if exists "$unit"; then
        if systemctl is-enabled "$unit" 2> /dev/null | grep -qE "^(enabled|indirect)"; then
            run systemctl disable --now "$unit"
            say "✅ $unit désactivé"
        else
            say "·  $unit déjà désactivé"
        fi
    fi
done

# 2. cloud-init : il n'a servi qu'au tout premier démarrage (réglages de Raspberry Pi Imager), il ralentit les suivants
if [ -d /etc/cloud ]; then
    if [ -f "$CLOUD_OFF" ]; then
        say "·  cloud-init déjà désactivé"
    else
        run touch "$CLOUD_OFF"
        say "✅ cloud-init désactivé (environ 10 s de démarrage en moins)"
    fi
fi

# 3. Écritures disque regroupées : moins d'usure de la carte SD (données au plus 60 s en mémoire)
if [ -f "$SYSCTL" ]; then
    say "·  Écritures disque déjà regroupées"
else
    if [ "$MODE" = "dry" ]; then
        say "   (aperçu) écriture de $SYSCTL"
    else
        printf '%s\n' "# Pimmich : écritures regroupées pour ménager la carte SD (voir utils/optimize_pi.sh)" \
            "vm.dirty_writeback_centisecs = 1500" "vm.dirty_expire_centisecs = 6000" > "$SYSCTL"
        sysctl --system > /dev/null
    fi
    say "✅ Écritures disque regroupées (toutes les 15 s au lieu de 5 s)"
fi

# 4. Démarrage : pas de recherche de caméra, pas d'écran arc-en-ciel (sauvegarde de config.txt avant)
if [ -f "$CONFIG" ]; then
    [ "$MODE" = "apply" ] && [ ! -f "$BACKUP" ] && cp "$CONFIG" "$BACKUP"
    if grep -q "^camera_auto_detect=1" "$CONFIG"; then
        run sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' "$CONFIG"
        say "✅ Détection de caméra désactivée"
    fi
    if ! grep -q "^disable_splash=1" "$CONFIG"; then
        if [ "$MODE" = "dry" ]; then
            say "   (aperçu) ajout de disable_splash=1 dans $CONFIG"
        else
            printf '\n[all]\n# Pimmich : pas d écran arc-en-ciel au démarrage\ndisable_splash=1\n' >> "$CONFIG"
        fi
        say "✅ Écran arc-en-ciel du démarrage supprimé"
    fi
fi

say ""
if [ "$MODE" = "dry" ]; then
    say "Aperçu seulement : rien n'a été changé. Pour appliquer : sudo $0"
else
    say "Terminé. Redémarrez pour en profiter : sudo reboot"
    say "Pour revenir en arrière : sudo $0 --undo"
fi
