#!/bin/bash
# Installe Pimmich « événement » sur un Mac : Python, ffmpeg (vidéos, GIF), mpv (lecture des vidéos), puis les
# bibliothèques de Pimmich dans un environnement à part (.venv). À lancer une fois, depuis le dossier de Pimmich :
#   bash desktop/install_mac.sh
# Ensuite : double-clic sur « Pimmich événement.command » (ou : .venv/bin/python pimmich_event.py).
set -e
cd "$(dirname "$0")/.."
if ! command -v brew > /dev/null; then
    echo "Homebrew est nécessaire : https://brew.sh (copiez la commande d'installation dans le Terminal), puis relancez ce script."
    exit 1
fi
echo "=== Python, ffmpeg et mpv (Homebrew) ==="
brew install python@3.12 python-tk@3.12 ffmpeg mpv
PYTHON="$(brew --prefix)/bin/python3.12"
echo "=== Bibliothèques de Pimmich (.venv) ==="
"$PYTHON" -m venv .venv
.venv/bin/pip install --upgrade pip > /dev/null
.venv/bin/pip install -r requirements.txt
cat > "Pimmich événement.command" << 'LAUNCH'
#!/bin/bash
cd "$(dirname "$0")" && exec .venv/bin/python pimmich_event.py
LAUNCH
chmod +x "Pimmich événement.command"
echo ""
echo "✅ Pimmich est installé. Pour le lancer : double-clic sur « Pimmich événement.command »."
echo "   Au premier lancement, macOS demande d'autoriser les connexions entrantes : acceptez (les invités en ont besoin)."
