"""
Livre d'or : les messages et dessins des invités restent consultables après avoir quitté le diaporama
(les messages d'invités expirent au bout de quelques jours, le livre d'or les garde).
"""
import json
import threading
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
STORE = BASE_DIR / "config" / "guestbook.json"
IMAGES_DIR = BASE_DIR / "static" / "guestbook"
_lock = threading.Lock()


def _load():
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(entries):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STORE)


def archive(message, image_path):
    """Garde un message (ou dessin) d'invité dans le livre d'or, avec une image réduite."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image.thumbnail((960, 960))
            image.save(IMAGES_DIR / f"{message['id']}.jpg", "JPEG", quality=82)
    except OSError:
        return None
    entry = {"id": message["id"], "kind": message.get("kind", "text"), "title": message.get("title", ""), "body": message.get("body", ""),
             "signature": message.get("signature", ""), "created": message.get("created", "")}
    with _lock:
        entries = [e for e in _load() if e["id"] != entry["id"]]
        entries.append(entry)
        _save(entries)
    return entry


def entries():
    """Pages du livre d'or, les plus récentes d'abord."""
    return sorted(_load(), key=lambda e: e.get("created", ""), reverse=True)


def delete(entry_id):
    with _lock:
        all_entries = _load()
        remaining = [e for e in all_entries if e["id"] != entry_id]
        _save(remaining)
    (IMAGES_DIR / f"{entry_id}.jpg").unlink(missing_ok=True)
    return len(remaining) != len(all_entries)
