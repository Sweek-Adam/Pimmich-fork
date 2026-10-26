"""
Commentaires des invités sur la photo affichée (« Quel souvenir ! ») : envoyés depuis la page invités, ils s'affichent
aussitôt en bandeau sur le cadre, et le dernier revient quand la photo repasse. Gardés dans cache/photo_comments.json.
"""
import json
import threading
import time
from pathlib import Path

from utils.platform_info import tmp_path

STORE = Path(__file__).resolve().parent.parent / "cache" / "photo_comments.json"
EVENT_FILE = tmp_path("pimmich_comment.json")  # dernier commentaire, pour le bandeau (hors carte SD)
MAX_LENGTH = 120
PER_PHOTO = 20
_lock = threading.Lock()


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def clean(text):
    return " ".join(str(text or "").split())[:MAX_LENGTH]


def add(photo, text, name=""):
    """Ajoute un commentaire (photo : chemin relatif à static/, ex. prepared/gdrive/x.jpg) ; ValueError s'il est vide."""
    text = clean(text)
    if not text:
        raise ValueError("Commentaire vide.")
    entry = {"text": text, "name": clean(name)[:40], "at": time.time()}
    with _lock:
        data = _load()
        data[photo] = (data.get(photo, []) + [entry])[-PER_PHOTO:]
        _save(data)
    try:
        Path(str(EVENT_FILE)).write_text(json.dumps(dict(entry, photo=photo), ensure_ascii=False))
    except OSError:
        pass
    return entry


def for_photo(photo):
    return list(_load().get(photo, []))


def latest(photo):
    items = for_photo(photo)
    return items[-1] if items else None


def latest_event(since):
    try:
        event = json.loads(Path(str(EVENT_FILE)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return event if event.get("at", 0) > since else None


def delete(photo, at):
    with _lock:
        data = _load()
        kept = [c for c in data.get(photo, []) if abs(c["at"] - float(at)) > 1e-6]
        if len(kept) == len(data.get(photo, [])):
            return False
        if kept:
            data[photo] = kept
        else:
            data.pop(photo, None)
        _save(data)
    return True
