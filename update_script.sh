#!/bin/bash
# Ce script est exécuté par l'application web pour se mettre à jour.
# Il ne doit pas redémarrer de service lui-même, car l'application web
# se chargera de se terminer pour être relancée par son superviseur (systemd, etc.).

set -e # Arrête le script si une commande échoue

# Se placer dans le répertoire racine de Pimmich
cd "$(dirname "$0")"
REPO_DIR=$(pwd)

# Usage : update_script.sh                 → dernière version de GitHub
#         update_script.sh --rollback SHA   → retour à une version précise (version précédente)
TARGET="origin/main"
MODE="update"
if [ "$1" = "--rollback" ] && [ -n "$2" ]; then
    MODE="rollback"
    TARGET="$2"
    shift 2
fi

# PROTECTION CRITIQUE : S'exécuter depuis /tmp pour survivre à l'écrasement par git reset
if [ "$1" != "--safe-run" ]; then
    cp "$0" /tmp/pimmich_update_safe.sh
    chmod +x /tmp/pimmich_update_safe.sh
    exec /tmp/pimmich_update_safe.sh --safe-run "$REPO_DIR" "$MODE" "$TARGET"
else
    cd "$2"
    MODE="${3:-update}"
    TARGET="${4:-origin/main}"
fi
case "$TARGET" in
    origin/main|[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
    *) echo "STEP:ERROR:Version invalide : $TARGET"; exit 1 ;;
esac

# Bloc de protection pour sauvegarder/restaurer la config malgré le reset git
{
    echo "--- Sauvegarde de la configuration locale ---"
    BACKUP_DIR="/tmp/pimmich_conf_backup"
    rm -rf "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    if [ -d "config" ]; then
        cp -a config "$BACKUP_DIR/"
    fi

    echo "STEP:PULL:--- Étape 1/2: Téléchargement des mises à jour (git) ---"
    PREVIOUS=$(git rev-parse HEAD)
    # Utilise une méthode robuste qui évite les blocages dus aux conflits locaux.
    git fetch --all
    git reset --hard "$TARGET"
    # Version d'avant notée : retour automatique si la nouvelle ne démarre pas (start_pimmich.sh)
    if [ "$MODE" = "update" ]; then
        printf '{"previous": "%s", "target": "%s", "status": "pending", "started": %s}\n' "$PREVIOUS" "$(git rev-parse HEAD)" "$(date +%s)" > "$BACKUP_DIR/.update_state.json"
    else
        printf '{"previous": "%s", "target": "%s", "status": "rolled_back", "started": %s}\n' "$PREVIOUS" "$(git rev-parse HEAD)" "$(date +%s)" > "$BACKUP_DIR/.update_state.json"
    fi
    
    # Rétablir les permissions d'exécution (git reset peut les faire sauter)
    echo "--- Correction des permissions ---"
    chmod +x *.sh 2>/dev/null || true

    echo "--- Restauration de la configuration locale ---"
    if [ -d "$BACKUP_DIR/config" ]; then
        # On restaure le contenu en écrasant les fichiers par défaut du repo
        cp -a "$BACKUP_DIR/config/." config/
    fi
    [ -f "$BACKUP_DIR/.update_state.json" ] && cp "$BACKUP_DIR/.update_state.json" config/.update_state.json
    
    rm -rf "$BACKUP_DIR"
}

echo "STEP:PIP:--- Étape 2/2: Mise à jour des dépendances Python ---"
source venv/bin/activate

# Rediriger la sortie de pip vers un fichier de log pour le débogage
# et vérifier le code de retour manuellement pour ne pas bloquer le redémarrage.
# pygame remplacé par pygame-ce (même « import pygame ») : les deux ne peuvent pas coexister
if grep -q "^pygame-ce" requirements.txt && pip show pygame > /dev/null 2>&1; then
    pip uninstall -y pygame >> logs/update_pip.log 2>&1 || true
fi
if ! pip install --timeout 60 -r requirements.txt > logs/update_pip.log 2>&1; then
    echo "STEP:WARNING:--- AVERTISSEMENT: La mise à jour des dépendances a échoué. ---"
    echo "STEP:WARNING:L'application va quand même redémarrer, mais pourrait être instable."
    echo "STEP:WARNING:Consultez le fichier 'logs/update_pip.log' depuis l'onglet Système pour les détails."
fi

echo "--- Réapplication des règles Sway pour mpv et python3 ---"
SWAY_CONFIG_DIR="$HOME/.config/sway"
SWAY_CONFIG_FILE="$SWAY_CONFIG_DIR/config"

# Utiliser tee -a avec sudo pour ajouter les lignes si elles ne sont pas déjà présentes
grep -q 'for_window \[app_id="mpv"\]' "$SWAY_CONFIG_FILE" || echo 'for_window [app_id="mpv"] floating enable, border none, fullscreen enable' | sudo tee -a "$SWAY_CONFIG_FILE" > /dev/null
grep -q 'for_window \[class="python3"\]' "$SWAY_CONFIG_FILE" || echo 'for_window [class="python3"] floating enable, border none, fullscreen enable' | sudo tee -a "$SWAY_CONFIG_FILE" > /dev/null

# Recharger la configuration Sway pour appliquer les changements immédiatement
export SWAYSOCK=$(ls /run/user/$(id -u)/sway-ipc.* | head -n 1) # Trouver le socket Sway
swaymsg reload || true # Utiliser || true pour ne pas faire échouer le script si swaymsg échoue (ex: pas de session Sway)

echo "STEP:RESTART:Mise à jour des fichiers terminée. L'application va redémarrer."