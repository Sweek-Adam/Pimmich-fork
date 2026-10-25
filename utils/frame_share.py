"""
Cadres jumelés : les nouveautés reçues par ce cadre partent aussi, automatiquement, vers les cadres de la famille
choisis (photos envoyées par la famille et les invités, messages écrits sur le cadre).

- Désactivé par défaut, cadre par cadre ; seules les nouveautés arrivées après l'activation sont partagées.
- Jamais de boucle : ce qui vient d'un autre cadre (source « cadres », messages reçus d'un cadre) ne repart pas.
- Les photos des bibliothèques en ligne (Google Drive, Immich, iCloud...) ne sont pas recopiées : l'autre cadre peut
  s'y connecter lui-même.
"""
import json
import threading
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_DIR / "cache" / "frame_share.json"
NOT_SHARED = {"cadres", "gdrive", "immich", "samba", "cloud", "icloud", "personnes", "usb", "messages"}
MAX_BYTES = 150 * 1024 * 1024  # par envoi (le cadre qui reçoit accepte 200 Mo) : une vidéo plus lourde reste ici
BATCH = 5
_lock = threading.Lock()


def shared_source(source):
    return source not in NOT_SHARED and not source.startswith(".")


def _load():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def pending_photos(frame, photos_dir, is_media):
    """Photos et vidéos à envoyer à ce cadre : [(source, nom, chemin)], les plus anciennes d'abord."""
    since = float(frame.get("share_since") or time.time())
    sent = set(_load().get(frame["id"], {}).get("photos", []))
    found = []
    for folder in Path(photos_dir).iterdir() if Path(photos_dir).is_dir() else []:
        if not folder.is_dir() or not shared_source(folder.name):
            continue
        for path in folder.iterdir():
            try:
                stat = path.stat()
            except OSError:
                continue
            key = f"{folder.name}/{path.name}"
            if path.is_file() and is_media(path.name) and stat.st_mtime >= since and key not in sent and stat.st_size <= MAX_BYTES:
                found.append((stat.st_mtime, folder.name, path.name, path))
    return [(s, n, p) for _m, s, n, p in sorted(found)]


def batches(items):
    """Paquets d'au plus BATCH fichiers et MAX_BYTES octets."""
    batch, size = [], 0
    for item in items:
        weight = item[2].stat().st_size
        if batch and (len(batch) >= BATCH or size + weight > MAX_BYTES):
            yield batch
            batch, size = [], 0
        batch.append(item)
        size += weight
    if batch:
        yield batch


def pending_messages(frame, messages):
    """Messages écrits à envoyer à ce cadre (pas ceux reçus d'un autre cadre, ni les dessins ou messages vocaux)."""
    since = float(frame.get("share_since") or time.time())
    sent = set(_load().get(frame["id"], {}).get("messages", []))
    out = []
    for message in messages:
        if message.get("from_frame") or message.get("kind") in ("drawing", "voice") or message["id"] in sent:
            continue
        try:
            created = time.mktime(time.strptime(message.get("created", ""), "%Y-%m-%d %H:%M"))
        except ValueError:
            continue
        if created >= since - 60:  # « created » est à la minute près
            out.append(message)
    return out


def mark_sent(frame_id, photos=(), messages=()):
    with _lock:
        state = _load()
        entry = state.setdefault(frame_id, {"photos": [], "messages": []})
        entry["photos"] = (entry.get("photos", []) + list(photos))[-5000:]
        entry["messages"] = (entry.get("messages", []) + list(messages))[-1000:]
        _save(state)


def counts(frame_id):
    entry = _load().get(frame_id, {})
    return {"photos": len(entry.get("photos", [])), "messages": len(entry.get("messages", []))}


def forget(frame_id):
    with _lock:
        state = _load()
        if state.pop(frame_id, None) is not None:
            _save(state)
