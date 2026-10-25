"""
Souvenirs vocaux : l'histoire d'une photo racontée de vive voix (« c'était l'été où... »), enregistrée depuis le
téléphone. Quand la photo passe sur le cadre, l'enregistrement est lu (la musique s'efface derrière la voix) et la
photo reste affichée le temps de l'écouter.

Enregistrements dans cache/photo_voices/ (Ogg Vorbis), liste dans index.json : {clé de la photo: {id, auteur,
secondes, date}} ; la clé est celle de l'index des photos (source/nom, variantes polaroïd ramenées à la photo).
"""
import json
import secrets
import threading
from datetime import datetime
from pathlib import Path

from utils import messages_manager

PROJECT_DIR = Path(__file__).resolve().parent.parent
VOICE_DIR = PROJECT_DIR / "cache" / "photo_voices"
INDEX_FILE = VOICE_DIR / "index.json"
_lock = threading.Lock()


def key_for(path):
    from utils import photo_index
    return photo_index.key_for(path)


def load():
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(index):
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INDEX_FILE)


def path_for(key, index=None):
    entry = (index if index is not None else load()).get(key)
    if not entry:
        return None
    path = VOICE_DIR / f"{entry['id']}.ogg"
    return path if path.exists() else None


def save(key, data, author=""):
    """Enregistre (ou remplace) le souvenir vocal d'une photo ; retourne sa durée en secondes."""
    voice_id = secrets.token_hex(6)
    seconds = messages_manager.encode_voice(data, VOICE_DIR / f"{voice_id}.ogg")
    with _lock:
        index = load()
        old = index.get(key)
        index[key] = {"id": voice_id, "author": str(author or "")[:60], "seconds": seconds, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
        _save(index)
    if old:
        (VOICE_DIR / f"{old['id']}.ogg").unlink(missing_ok=True)
    return seconds


def delete(key):
    with _lock:
        index = load()
        old = index.pop(key, None)
        if old:
            _save(index)
    if old:
        (VOICE_DIR / f"{old['id']}.ogg").unlink(missing_ok=True)
    return bool(old)
