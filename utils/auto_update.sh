#!/bin/bash
# Mise à jour automatique (lancée chaque jour par la crontab, voir utils/enable_auto_update.sh) :
# - Pimmich : s'il y a du nouveau sur GitHub, même mise à jour que le bouton de l'interface (update_script.sh),
#   puis relance de l'application ; si la nouvelle version plante au démarrage, start_pimmich.sh revient tout seul
#   à la précédente ;
# - avec --system : les paquets du système aussi (apt-get upgrade, sans redémarrage automatique).
# Tout est noté dans logs/auto_update.log. Rien n'est fait pendant une synchronisation (rclone) ou une autre mise à jour.

cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
LOG="logs/auto_update.log"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

SYSTEM=0
[ "$1" = "--system" ] && SYSTEM=1

# Une seule exécution à la fois
exec 9> /tmp/pimmich_auto_update.lock
flock -n 9 || exit 0

# Journal gardé court (les 1000 dernières lignes)
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 1000 ]; then
    tail -n 1000 "$LOG" > "$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
fi

if pgrep -f "[r]clone" > /dev/null; then
    log "Synchronisation en cours (rclone) : mise à jour reportée à demain."
    exit 0
fi
if pgrep -f "[p]immich_update_safe" > /dev/null; then
    log "Une mise à jour est déjà en cours : rien à faire."
    exit 0
fi

# --- Pimmich ---
if ! git fetch --quiet origin main 2>> "$LOG"; then
    log "GitHub injoignable : mise à jour de Pimmich reportée."
else
    BEHIND=$(git rev-list --count HEAD..origin/main 2> /dev/null || echo 0)
    if [ "$BEHIND" -gt 0 ]; then
        log "Pimmich : $BEHIND nouveauté(s) ($(git rev-parse --short HEAD) -> $(git rev-parse --short origin/main)), mise à jour..."
        if ./update_script.sh >> "$LOG" 2>&1; then
            # start_pimmich.sh relance l'application sur la nouvelle version (et revient à l'ancienne si elle plante)
            pkill -f "python3 -u app.py"
            log "Pimmich mis à jour ($(git rev-parse --short HEAD)) et relancé."
        else
            log "Échec de la mise à jour de Pimmich (détails ci-dessus) : la version actuelle est conservée."
        fi
    else
        log "Pimmich est à jour ($(git rev-parse --short HEAD))."
    fi
fi

# --- Système (option --system) ---
if [ "$SYSTEM" = 1 ] && pgrep -x "apt-get|apt|dpkg|unattended-upgr" > /dev/null; then
    log "Une autre mise à jour du système est en cours (apt) : la mise à jour du système est reportée à demain."
elif [ "$SYSTEM" = 1 ]; then
    # sans question (DEBIAN_FRONTEND) ; fichiers de configuration modifiés à la main conservés (confold)
    if sudo -n DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get update -q >> "$LOG" 2>&1 && \
       sudo -n DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get -y -q -o Dpkg::Options::=--force-confdef \
            -o Dpkg::Options::=--force-confold upgrade >> "$LOG" 2>&1; then
        log "Paquets du système à jour."
        [ -f /var/run/reboot-required ] && log "Un redémarrage est conseillé pour terminer certaines mises à jour du système."
    else
        log "Mise à jour du système impossible (droits sudo ? réseau ?) : voir ci-dessus."
    fi
fi
