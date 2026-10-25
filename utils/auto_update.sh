#!/bin/bash
# Mise à jour automatique (lancée chaque jour par la crontab, voir utils/enable_auto_update.sh) :
# - Pimmich : s'il y a du nouveau sur GitHub, même mise à jour que le bouton de l'interface (update_script.sh),
#   puis relance de l'application ; si la nouvelle version plante au démarrage, start_pimmich.sh revient tout seul
#   à la précédente ;
# - avec --system : tout le système aussi (apt-get full-upgrade, nouveaux noyaux compris, puis autoremove),
#   sans redémarrage automatique.
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
# Jamais pendant un travail lourd (encodage de la nuit, préparation), une fête ou une partie de jeu : la mise à jour
# redémarre Pimmich. On attend jusqu'à 2 heures, sinon ce sera pour la nuit suivante.
PYTHON=venv/bin/python
[ -x "$PYTHON" ] || PYTHON=python3
WAITED=0
while BUSY=$("$PYTHON" -m utils.busy 2> /dev/null); [ -n "$BUSY" ]; do
    if [ "$WAITED" -ge 7200 ]; then
        log "Cadre occupé ($BUSY) : mise à jour de Pimmich reportée à demain."
        SKIP_PIMMICH=1
        break
    fi
    [ "$WAITED" = 0 ] && log "Cadre occupé ($BUSY) : la mise à jour attend (2 heures au plus)."
    sleep 300
    WAITED=$((WAITED + 300))
done
if [ "${SKIP_PIMMICH:-0}" = 1 ]; then
    :
elif ! git fetch --quiet origin main 2>> "$LOG"; then
    log "GitHub injoignable : mise à jour de Pimmich reportée."
else
    BEHIND=$(git rev-list --count HEAD..origin/main 2> /dev/null || echo 0)
    if [ "$BEHIND" -gt 0 ]; then
        log "Pimmich : $BEHIND nouveauté(s) ($(git rev-parse --short HEAD) -> $(git rev-parse --short origin/main)), mise à jour..."
        if ./update_script.sh >> "$LOG" 2>&1; then
            # start_pimmich.sh relance l'application sur la nouvelle version (et revient à l'ancienne si elle plante)
            BUSY=$("$PYTHON" -m utils.busy 2> /dev/null)  # un travail a pu commencer pendant la mise à jour
            for _i in $(seq 1 24); do [ -z "$BUSY" ] && break; sleep 300; BUSY=$("$PYTHON" -m utils.busy 2> /dev/null); done
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
            -o Dpkg::Options::=--force-confold full-upgrade >> "$LOG" 2>&1; then
        # paquets devenus inutiles (anciens noyaux, dépendances orphelines) et archives téléchargées
        sudo -n DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get -y -q autoremove >> "$LOG" 2>&1 || log "Nettoyage (autoremove) impossible."
        sudo -n /usr/bin/apt-get -q autoclean >> "$LOG" 2>&1 || true
        log "Paquets du système à jour (et paquets inutiles retirés)."
        # Raspberry Pi OS ne crée pas toujours /var/run/reboot-required : on compare aussi le noyau installé à celui en cours
        NEWEST=$(ls /lib/modules 2> /dev/null | grep -- "$(uname -r | sed 's/^[0-9.]*//')$" | sort -V | tail -1)
        if [ -f /var/run/reboot-required ] || { [ -n "$NEWEST" ] && [ "$NEWEST" != "$(uname -r)" ]; }; then
            log "Un redémarrage est conseillé pour terminer les mises à jour du système (noyau ${NEWEST:-mis à jour})."
        fi
    else
        log "Mise à jour du système impossible (droits sudo ? réseau ?) : voir ci-dessus."
    fi
fi
