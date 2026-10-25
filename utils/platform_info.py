"""
Où tourne Pimmich ? Un Raspberry Pi (cadre photo) ou un ordinateur Mac / Windows / Linux (édition « événement » :
un portable qui affiche le diaporama sur un écran ou un vidéoprojecteur, pour un mariage par exemple).

  - tmp_path(nom) : fichiers d'échange en mémoire entre l'interface et le diaporama (/tmp sur le Raspberry Pi,
    le dossier temporaire du système ailleurs) ;
  - desktop() : édition ordinateur (pas de Wi-Fi géré, pas de sudo, pas de sway) ;
  - web_port() / guest_base_url() : adresse donnée aux invités (avec le port sur un ordinateur).
"""
import os
import sys
import tempfile
from pathlib import Path

WINDOWS = sys.platform.startswith("win")
MAC = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")


def desktop():
    """Édition ordinateur : demandée par le lanceur (PIMMICH_DESKTOP=1), ou tout système autre que Linux."""
    return os.environ.get("PIMMICH_DESKTOP") == "1" or not LINUX


def tmp_dir():
    if LINUX:
        return Path("/tmp")
    folder = Path(tempfile.gettempdir()) / "pimmich"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def tmp_path(name):
    """Fichier d'échange : /tmp/<nom> sur Linux (inchangé pour les scripts du cadre), sinon le dossier temporaire."""
    return tmp_dir() / name


def web_port():
    try:
        return int(os.environ.get("PIMMICH_PORT") or (8080 if desktop() else 80))
    except ValueError:
        return 8080 if desktop() else 80


def guest_base_url(host):
    """« http://adresse » pour les invités (QR codes), avec le port quand ce n'est pas 80."""
    port = web_port()
    return f"http://{host}" + ("" if port == 80 else f":{port}")
