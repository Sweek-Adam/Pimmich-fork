"""
Messages texte affichés comme des photos dans le diaporama (source « messages »).

Chaque message est enregistré dans config/messages.json et rendu en image dans static/prepared/messages/<id>.jpg,
à la résolution de l'écran. Un message peut avoir une date de fin : il est retiré automatiquement après ce jour.
"""
import json
import secrets
import threading
from datetime import date, datetime
from pathlib import Path

from utils.message_renderer import render_message, STYLES, DEFAULT_STYLE

PROJECT_DIR = Path(__file__).resolve().parent.parent
MESSAGES_FILE = PROJECT_DIR / "config" / "messages.json"
PREPARED_DIR = PROJECT_DIR / "static" / "prepared" / "messages"
SOURCE_NAME = "messages"
MAX_TITLE, MAX_BODY, MAX_SIGNATURE = 120, 1000, 80

_lock = threading.Lock()


def _load():
    try:
        return json.loads(MESSAGES_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def _save(messages):
    MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MESSAGES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(messages, indent=2, ensure_ascii=False))
    tmp.replace(MESSAGES_FILE)


def image_path(message_id):
    return PREPARED_DIR / f"{message_id}.jpg"


def validate(title, body, signature, style, expires):
    """Normalise les champs saisis ; lève ValueError si le message est invalide."""
    title, body, signature = (title or "").strip(), (body or "").strip(), (signature or "").strip()
    if not title and not body:
        raise ValueError("Le message doit contenir un titre ou un texte.")
    if len(title) > MAX_TITLE or len(body) > MAX_BODY or len(signature) > MAX_SIGNATURE:
        raise ValueError(f"Message trop long (titre {MAX_TITLE}, texte {MAX_BODY}, signature {MAX_SIGNATURE} caractères maximum).")
    if style not in STYLES:
        style = DEFAULT_STYLE
    if expires:
        try:
            expires_date = date.fromisoformat(expires)
        except ValueError:
            raise ValueError("Date de fin invalide.")
        if expires_date < date.today():
            raise ValueError("La date de fin est déjà passée.")
        expires = expires_date.isoformat()
    else:
        expires = None
    return title, body, signature, style, expires


def preview(title, body, signature, style, width, height):
    title, body, signature, style, _ = validate(title, body, signature, style, None)
    return render_message(title, body, signature, style, width, height)


def list_messages():
    """Messages existants (les plus récents d'abord) ; ceux dont l'image a été supprimée sont oubliés."""
    with _lock:
        messages = _load()
        kept = [m for m in messages if image_path(m["id"]).exists()]
        if len(kept) != len(messages):
            _save(kept)
    return sorted(kept, key=lambda m: m.get("created", ""), reverse=True)


def create_message(title, body, signature, style, expires, author, width, height):
    title, body, signature, style, expires = validate(title, body, signature, style, expires)
    message = {
        "id": secrets.token_hex(6),
        "title": title, "body": body, "signature": signature, "style": style, "expires": expires,
        "author": author or "", "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    render_message(title, body, signature, style, width, height).save(image_path(message["id"]), "JPEG", quality=90)
    with _lock:
        messages = _load()
        messages.append(message)
        _save(messages)
    return message


def delete_message(message_id):
    """Supprime un message et son image ; retourne False s'il n'existait pas."""
    with _lock:
        messages = _load()
        remaining = [m for m in messages if m["id"] != message_id]
        _save(remaining)
    image_path(message_id).unlink(missing_ok=True)
    return len(remaining) != len(messages)


def delete_all_messages():
    with _lock:
        for m in _load():
            image_path(m["id"]).unlink(missing_ok=True)
        _save([])


def purge_expired(today=None):
    """Retire les messages dont la date de fin est passée ; retourne le nombre de messages retirés."""
    today = (today or date.today()).isoformat()
    with _lock:
        messages = _load()
        expired = [m for m in messages if m.get("expires") and m["expires"] < today]
        if expired:
            _save([m for m in messages if m not in expired])
    for m in expired:
        image_path(m["id"]).unlink(missing_ok=True)
    return len(expired)


def rerender_all(width, height):
    """Régénère les images (après un changement de résolution ou d'orientation de l'écran)."""
    for m in list_messages():
        render_message(m["title"], m["body"], m["signature"], m["style"], width, height).save(image_path(m["id"]), "JPEG", quality=90)
