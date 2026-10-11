"""
Historique : qui a envoyé quoi, ce qui a changé, ce qui a été affiché ; et annulation de la dernière action.

- Les actions (envois, messages, playlists, réglages, ambiances) sont notées dans cache/history.json (300 au plus) ;
  certaines gardent de quoi être annulées (ancienne configuration, playlist ou message supprimés) ;
- les photos affichées sont notées par le diaporama en mémoire vive (/tmp) : aucune écriture sur la carte SD.
"""
import json
import secrets
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORE = BASE_DIR / "cache" / "history.json"
UNDO_DIR = BASE_DIR / "cache" / "undo"
DISPLAYED = Path("/tmp/pimmich_displayed.json")
MAX_EVENTS = 300
MAX_DISPLAYED = 300
_lock = threading.Lock()
UNDO_HANDLERS = {}  # type d'annulation -> fonction(données) ; enregistrées par l'application


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(events):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE)


MERGE_SECONDS = 120


def record(kind, text, who="", undo=None, merge=False):
    """Note une action. `undo` : {"type": ..., "data": ...} (données gardées à part, pour pouvoir l'annuler).
    `merge` : une suite d'actions du même genre, par la même personne, en moins de 2 minutes, ne compte qu'une fois
    (l'annulation ramène alors à l'état d'avant la série)."""
    if merge:
        with _lock:
            previous = _load()
        last = previous[-1] if previous else None
        if last and last["kind"] == kind and last["who"] == str(who or "")[:60] and not last.get("undone") \
                and time.time() - last["at"] < MERGE_SECONDS:
            return last
    event = {"id": secrets.token_hex(5), "at": int(time.time()), "kind": kind, "text": str(text)[:200], "who": str(who or "")[:60]}
    if undo and undo.get("type") in UNDO_HANDLERS:
        UNDO_DIR.mkdir(parents=True, exist_ok=True)
        (UNDO_DIR / f"{event['id']}.json").write_text(json.dumps(undo, ensure_ascii=False), encoding="utf-8")
        event["undoable"] = True
    with _lock:
        events = (_load() + [event])[-MAX_EVENTS:]
        kept = {e["id"] for e in events}
        _save(events)
    for path in UNDO_DIR.glob("*.json") if UNDO_DIR.is_dir() else []:  # données d'annulation des actions oubliées
        if path.stem not in kept:
            path.unlink(missing_ok=True)
    return event


def events(limit=50):
    """Actions, les plus récentes d'abord."""
    return list(reversed(_load()))[:limit]


def last_undoable():
    return next((e for e in reversed(_load()) if e.get("undoable") and not e.get("undone")), None)


def undo_last(who=""):
    """Annule la dernière action annulable ; renvoie l'action annulée (ou None)."""
    event = last_undoable()
    if event is None:
        return None
    path = UNDO_DIR / f"{event['id']}.json"
    try:
        undo = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        undo = None
    if not undo or undo.get("type") not in UNDO_HANDLERS:
        raise ValueError("Cette action ne peut plus être annulée.")
    UNDO_HANDLERS[undo["type"]](undo.get("data"))
    with _lock:
        all_events = _load()
        for e in all_events:
            if e["id"] == event["id"]:
                e["undone"] = True
        _save(all_events)
    path.unlink(missing_ok=True)
    record("undo", f"↶ {event['text']}", who)
    return event


# --- Ce qui a été affiché (écrit par le diaporama, en mémoire vive) ---

def displayed(path):
    try:
        items = json.loads(DISPLAYED.read_text())
    except (OSError, ValueError):
        items = []
    items = (items + [{"path": str(path), "at": int(time.time())}])[-MAX_DISPLAYED:]
    try:
        DISPLAYED.write_text(json.dumps(items))
    except OSError:
        pass


def recently_displayed(limit=40):
    try:
        return list(reversed(json.loads(DISPLAYED.read_text())))[:limit]
    except (OSError, ValueError):
        return []
