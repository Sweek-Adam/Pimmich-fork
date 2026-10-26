#!/bin/bash
# Impression (photomaton de fête) : CUPS démarre seulement quand on imprime (activation par socket), puis s'arrête.
#   sudo ~/pimmich/utils/enable_printing.sh          active l'impression
#   sudo ~/pimmich/utils/enable_printing.sh --undo   la désactive (comme utils/optimize_pi.sh)
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo "À lancer avec sudo : sudo $0 $*"; exit 1; fi
if [ "${1:-}" = "--undo" ]; then
    systemctl disable --now cups.socket cups.service > /dev/null 2>&1 || true
    echo "✅ Impression désactivée."
    exit 0
fi
systemctl enable --now cups.socket > /dev/null
USER_NAME="${SUDO_USER:-$(logname 2> /dev/null || echo adam)}"
id -nG "$USER_NAME" | grep -qw lpadmin || usermod -aG lpadmin "$USER_NAME"
echo "✅ Impression activée : choisissez l'imprimante dans Partage › Photomaton."
