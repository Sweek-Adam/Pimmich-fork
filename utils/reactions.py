"""
Réactions des invités : un ❤️ (ou 😂, 😮, 👏) sur la photo affichée en ce moment, depuis le téléphone (réseau de la
maison seulement). Le cadre fait s'envoler la réaction sur la photo, et les photos les plus aimées sont retenues.
"""
import json
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORE = BASE_DIR / "cache" / "reactions.json"
EVENT_FILE = Path("/tmp/pimmich_reaction.json")  # dernière réaction, pour l'animation (hors carte SD)
KINDS = {"love": "❤️", "laugh": "😂", "wow": "😮", "bravo": "👏"}
RECENT = 200
_lock = threading.Lock()


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"photos": {}, "recent": []}


def _save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


def add(photo, kind, who=""):
    """Enregistre une réaction sur une photo (chemin relatif à static/, ex. prepared/gdrive/x.jpg)."""
    if kind not in KINDS:
        raise ValueError("Réaction inconnue.")
    with _lock:
        data = _load()
        counts = data["photos"].setdefault(photo, {})
        counts[kind] = counts.get(kind, 0) + 1
        data["recent"] = ([{"photo": photo, "kind": kind, "who": who[:40], "at": int(time.time())}] + data["recent"])[:RECENT]
        _save(data)
    try:
        EVENT_FILE.write_text(json.dumps({"photo": photo, "kind": kind, "at": time.time()}))
    except OSError:
        pass
    return counts


def counts(photo):
    return dict(_load()["photos"].get(photo, {}))


def recent(limit=50):
    return _load()["recent"][:limit]


def most_loved(limit=20):
    """Photos les plus aimées : [(chemin, total)]."""
    photos = _load()["photos"]
    ranked = sorted(((p, sum(c.values())) for p, c in photos.items()), key=lambda x: -x[1])
    return ranked[:limit]


def latest_event(since):
    """Réaction arrivée après `since` (horodatage) : {photo, kind, at} ou None."""
    try:
        event = json.loads(EVENT_FILE.read_text())
    except (OSError, ValueError):
        return None
    return event if event.get("at", 0) > since else None
