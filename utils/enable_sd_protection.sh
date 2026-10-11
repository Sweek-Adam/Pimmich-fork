#!/bin/bash
# Protège la carte SD (à lancer une fois : sudo ./utils/enable_sd_protection.sh, puis redémarrer)
#
# - log2ram : les journaux du système (/var/log) et de Pimmich (logs/) sont écrits en mémoire vive et recopiés sur la
#   carte une fois par jour et à l'arrêt, au lieu de l'être en continu ;
# - journald limité (taille et durée) ;
# - option --zram : remplace le fichier d'échange sur la carte par une mémoire d'échange compressée en RAM.
# Pimmich garde déjà en /tmp (RAM) ce qui change souvent : photos affichées, battement du diaporama, musique en cours.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Ce script doit être lancé avec sudo : sudo $0" >&2
    exit 1
fi

PIMMICH_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- log2ram (dépôt de son auteur, signé) ---
if ! dpkg -s log2ram >/dev/null 2>&1; then
    echo "Installation de log2ram..."
    wget -qO /usr/share/keyrings/azlux-archive-keyring.gpg https://azlux.fr/repo.gpg
    echo "deb [signed-by=/usr/share/keyrings/azlux-archive-keyring.gpg] http://packages.azlux.fr/debian/ bookworm main" \
        > /etc/apt/sources.list.d/azlux.list
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq log2ram rsync
fi
CONF=/etc/log2ram.conf
sed -i -E "s|^SIZE=.*|SIZE=128M|" "$CONF"
sed -i -E "s|^PATH_DISK=.*|PATH_DISK=\"/var/log;${PIMMICH_DIR}/logs\"|" "$CONF"
sed -i -E "s|^USE_RSYNC=.*|USE_RSYNC=true|" "$CONF"
grep -q '^LOG_DISK_SIZE=' "$CONF" && sed -i -E "s|^LOG_DISK_SIZE=.*|LOG_DISK_SIZE=256M|" "$CONF"
systemctl enable log2ram >/dev/null 2>&1 || true

# --- journald : taille et durée limitées ---
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/pimmich.conf <<'EOL'
# Généré par utils/enable_sd_protection.sh : journaux limités (ils vivent en mémoire vive avec log2ram)
[Journal]
SystemMaxUse=40M
RuntimeMaxUse=40M
MaxRetentionSec=2week
EOL
journalctl --vacuum-size=40M >/dev/null 2>&1 || true

# --- Option : mémoire d'échange compressée en RAM au lieu d'un fichier sur la carte ---
if [ "${1:-}" = "--zram" ]; then
    if dpkg -s rpi-swap >/dev/null 2>&1; then
        # Raspberry Pi OS récent : rpi-swap gère déjà la zram ; on lui demande la zram seule (pas de fichier sur la carte)
        mkdir -p /etc/rpi/swap.conf.d
        printf '# Généré par utils/enable_sd_protection.sh : zram seule, aucun fichier d'\''échange sur la carte\n[Main]\nMechanism=zram\n' \
            > /etc/rpi/swap.conf.d/pimmich.conf
    else
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq zram-tools
        sed -i -E "s|^#?ALGO=.*|ALGO=zstd|; s|^#?PERCENT=.*|PERCENT=50|" /etc/default/zramswap
        systemctl enable zramswap >/dev/null 2>&1 || true
        systemctl disable --now dphys-swapfile >/dev/null 2>&1 || true
    fi
    # Fichiers d'échange déclarés dans /etc/fstab : désactivés (mis en commentaire, sauvegarde dans fstab.bak)
    if grep -qE '^[^#].*[[:space:]]swap[[:space:]]' /etc/fstab; then
        cp /etc/fstab /etc/fstab.bak
        sed -i -E 's|^([^#].*[[:space:]]swap[[:space:]].*)$|# (désactivé par Pimmich, remplacé par zram) \1|' /etc/fstab
    fi
fi

echo "✅ Protection de la carte SD configurée. Redémarrez le cadre pour l'activer : sudo reboot"
