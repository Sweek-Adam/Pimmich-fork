"""
Messages texte affichés comme des photos dans le diaporama (source « messages »).

Chaque message est enregistré dans config/messages.json et rendu en image dans static/prepared/messages/<id>.jpg,
à la résolution de l'écran. Un message peut avoir une date de fin : il est retiré automatiquement après ce jour.
"""
import io
import json
import secrets
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from utils.message_renderer import render_message, STYLES, DEFAULT_STYLE

PROJECT_DIR = Path(__file__).resolve().parent.parent
MESSAGES_FILE = PROJECT_DIR / "config" / "messages.json"
PREPARED_DIR = PROJECT_DIR / "static" / "prepared" / "messages"
# Messages masqués : leur image est rangée hors du dossier lu par le diaporama
HIDDEN_DIR = PROJECT_DIR / "static" / "messages_hidden"
# File des médias à afficher en priorité au prochain démarrage du diaporama (le plus récent en premier)
PRIORITY_FILE = PROJECT_DIR / "cache" / "priority_media.json"
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


def image_path(message_id, hidden=False):
    return (HIDDEN_DIR if hidden else PREPARED_DIR) / f"{message_id}.jpg"


def _path(message, now=None):
    """Image du message : dans le diaporama, ou de côté s'il est masqué (à la main, ou hors de sa plage programmée)."""
    return image_path(message["id"], message.get("hidden", False) or not on_air(message, now))


# --- Messages programmés (« le 12 mars à 8 h : Joyeux anniversaire Mamie »), éventuellement répétés ---

REPEATS = ("none", "daily", "weekly", "monthly", "yearly")
DURATIONS = (1, 2, 3, 6, 12, 24, 48, 72, 168)  # heures d'affichage à chaque fois


def validate_schedule(starts, repeat, duration_hours):
    """Programmation normalisée (début, répétition, durée en heures) ; None si le message n'est pas programmé."""
    if not starts:
        return None
    try:
        start = datetime.fromisoformat(str(starts)[:16])
    except ValueError:
        raise ValueError("Date de début invalide.")
    repeat = repeat if repeat in REPEATS else "none"
    try:
        duration = int(duration_hours or 24)
    except (TypeError, ValueError):
        duration = 24
    duration = duration if duration in DURATIONS else 24
    if repeat == "none" and start + timedelta(hours=duration) < datetime.now():
        raise ValueError("Cette programmation est déjà passée.")
    return {"starts": start.strftime("%Y-%m-%dT%H:%M"), "repeat": repeat, "duration_hours": duration}


def _occurrence(start, repeat, now):
    """Dernier passage (début) avant `now`, ou None si le message n'a pas encore commencé."""
    if now < start:
        return None
    if repeat == "daily":
        return start + timedelta(days=(now - start).days)
    if repeat == "weekly":
        return start + timedelta(weeks=(now - start).days // 7)
    if repeat in ("monthly", "yearly"):
        step = 1 if repeat == "monthly" else 12
        months = (now.year - start.year) * 12 + now.month - start.month
        months -= months % step
        for back in (0, step):
            total = start.month - 1 + months - back
            year, month = start.year + total // 12, total % 12 + 1
            day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            candidate = start.replace(year=year, month=month, day=day)
            if candidate <= now:
                return candidate
        return None
    return start


def on_air(message, now=None):
    """Le message doit-il être dans le diaporama en ce moment ? (toujours, s'il n'est pas programmé)"""
    schedule = message.get("schedule")
    if not schedule:
        return True
    now = now or datetime.now()
    start = datetime.fromisoformat(schedule["starts"])
    last = _occurrence(start, schedule.get("repeat", "none"), now)
    return last is not None and now < last + timedelta(hours=int(schedule.get("duration_hours", 24)))


def refresh_schedule(now=None):
    """Fait entrer et sortir les messages programmés du diaporama ; renvoie ceux qui viennent d'apparaître."""
    shown = []
    for message in list_messages():
        if not message.get("schedule"):
            continue
        visible_path, hidden_path = image_path(message["id"]), image_path(message["id"], True)
        target = _path(message, now)
        source = hidden_path if target == visible_path else visible_path
        if source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            if target == visible_path:
                push_priority(visible_path)  # à l'heure dite : affiché tout de suite
                shown.append(message)
    return shown


def _unlink_drawing(message_id):
    (PROJECT_DIR / "cache" / "drawings" / f"{message_id}.png").unlink(missing_ok=True)
    (PROJECT_DIR / "cache" / "voice" / f"{message_id}.ogg").unlink(missing_ok=True)


def _unlink_images(message_id):
    image_path(message_id).unlink(missing_ok=True)
    image_path(message_id, hidden=True).unlink(missing_ok=True)
    _unlink_drawing(message_id)


# --- File prioritaire : un nouveau message passe avant les autres (dernier arrivé, premier affiché) ---

def push_priority(path):
    with _lock:
        try:
            queue = json.loads(PRIORITY_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            queue = []
        queue = [str(path)] + [p for p in queue if p != str(path)]
        PRIORITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PRIORITY_FILE.write_text(json.dumps(queue[:50]))


def pop_priority():
    """Retourne la file (le plus récent en premier) et la vide : chaque média n'est prioritaire qu'une fois."""
    with _lock:
        try:
            queue = json.loads(PRIORITY_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            return []
        PRIORITY_FILE.unlink(missing_ok=True)
    return [p for p in queue if Path(p).exists()]


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
    """Messages existants, les plus récents d'abord."""
    with _lock:
        messages = _load()
    return sorted(messages, key=lambda m: m.get("created", ""), reverse=True)


GUEST_MAX_DAYS = 7  # durée d'affichage maximale d'un message d'invité


def create_message(title, body, signature, style, expires, author, width, height, guest=False, schedule=None):
    title, body, signature, style, expires = validate(title, body, signature, style, expires)
    if guest:
        # Les messages des invités s'affichent sans validation : ils expirent toujours au bout de GUEST_MAX_DAYS jours
        latest = (date.today() + timedelta(days=GUEST_MAX_DAYS)).isoformat()
        expires = min(expires, latest) if expires else latest
    message = {
        "id": secrets.token_hex(6),
        "title": title, "body": body, "signature": signature, "style": style, "expires": expires,
        "author": author or "", "guest": guest, "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if schedule:
        message["schedule"] = schedule
        if schedule["repeat"] == "none" and not expires:  # message unique : retiré une fois passé
            message["expires"] = (datetime.fromisoformat(schedule["starts"]) + timedelta(hours=schedule["duration_hours"])).date().isoformat()
    path = _path(message)
    path.parent.mkdir(parents=True, exist_ok=True)
    render_message(title, body, signature, style, width, height).save(path, "JPEG", quality=90)
    with _lock:
        messages = _load()
        messages.append(message)
        _save(messages)
    if on_air(message):
        push_priority(path)
    if guest:
        _archive(message, path)
    return message


def _archive(message, path):
    try:
        from utils import guestbook
        guestbook.archive(message, path)
    except Exception:
        pass  # le livre d'or ne doit jamais empêcher un message de s'afficher


def _update(message_id, **fields):
    with _lock:
        messages = _load()
        for m in messages:
            if m["id"] == message_id:
                m.update(fields)
                _save(messages)
                return m
    raise ValueError("Message introuvable.")


def set_expires(message_id, expires):
    """Change la date de fin d'affichage (None : sans limite)."""
    if expires:
        try:
            expires_date = date.fromisoformat(expires)
        except ValueError:
            raise ValueError("Date de fin invalide.")
        if expires_date < date.today():
            raise ValueError("La date de fin est déjà passée.")
        expires = expires_date.isoformat()
    return _update(message_id, expires=expires or None)


def set_hidden(message_id, hidden):
    """Masque ou réaffiche un message dans le diaporama sans le supprimer."""
    message = _update(message_id, hidden=bool(hidden))
    target = _path(message)  # un message programmé réaffiché attend sa plage horaire
    for source in (image_path(message_id), image_path(message_id, True)):
        if source != target and source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
    return message


def delete_message(message_id):
    """Supprime un message et son image ; retourne False s'il n'existait pas."""
    with _lock:
        messages = _load()
        remaining = [m for m in messages if m["id"] != message_id]
        _save(remaining)
    _unlink_images(message_id)
    return len(remaining) != len(messages)


def delete_all_messages():
    with _lock:
        for m in _load():
            _unlink_images(m["id"])
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
        _unlink_images(m["id"])
    return len(expired)


def _render_to_file(m, width, height):
    _path(m).parent.mkdir(parents=True, exist_ok=True)
    if m.get("kind") == "drawing":
        render_drawing(m["id"], m.get("signature", ""), width, height).save(_path(m), "JPEG", quality=90)
        return
    if m.get("kind") == "voice":
        render_voice_card(m, width, height).save(_path(m), "JPEG", quality=90)
        return
    render_message(m["title"], m["body"], m["signature"], m["style"], width, height).save(_path(m), "JPEG", quality=90)


# --- Dessins (à main levée, avec autocollants) envoyés depuis un téléphone ---

DRAWINGS_DIR = PROJECT_DIR / "cache" / "drawings"
MAX_DRAWING_BYTES = 6 * 1024 * 1024


def render_drawing(message_id, signature, width, height):
    """Le dessin sur l'écran entier : posé sur un fond doux, avec la signature de l'invité."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    from utils.message_renderer import _font, SERIF_ITALIC
    with Image.open(DRAWINGS_DIR / f"{message_id}.png") as drawing:
        drawing = drawing.convert("RGB")
    background = ImageOps.fit(drawing, (max(1, width // 8), max(1, height // 8))).filter(ImageFilter.GaussianBlur(3)).resize((width, height))
    background = Image.blend(background, Image.new("RGB", (width, height), (245, 240, 230)), 0.55)
    margin = int(min(width, height) * 0.06)
    fitted = ImageOps.contain(drawing, (width - 2 * margin, height - 2 * margin - (int(height * 0.06) if signature else 0)))
    x, y = (width - fitted.width) // 2, margin
    shadow = Image.new("RGBA", (fitted.width + 40, fitted.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([20, 24, fitted.width + 20, fitted.height + 24], fill=(0, 0, 0, 90))
    background.paste(shadow.filter(ImageFilter.GaussianBlur(12)), (x - 20, y - 20), shadow.filter(ImageFilter.GaussianBlur(12)))
    background.paste(fitted, (x, y))
    if signature:
        font = _font(SERIF_ITALIC, int(height * 0.045))
        ImageDraw.Draw(background).text((x + fitted.width, y + fitted.height + int(height * 0.012)), f"— {signature}",
                                        font=font, fill=(70, 60, 50), anchor="ra")
    return background


def create_drawing(data, signature, author, width, height, guest=True):
    """Enregistre un dessin (PNG ou JPEG envoyé par le téléphone) et l'ajoute au diaporama comme un message."""
    from PIL import Image
    if not data or len(data) > MAX_DRAWING_BYTES:
        raise ValueError("Dessin vide ou trop lourd.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            if image.width < 50 or image.height < 50 or image.width > 4096 or image.height > 4096:
                raise ValueError("Taille de dessin inattendue.")
            drawing = image.convert("RGB")
    except (OSError, SyntaxError):
        raise ValueError("Ce fichier n'est pas une image.")
    signature = (signature or "").strip()[:MAX_SIGNATURE]
    message = {"id": secrets.token_hex(6), "kind": "drawing", "title": "", "body": "", "signature": signature, "style": DEFAULT_STYLE,
               "expires": (date.today() + timedelta(days=GUEST_MAX_DAYS)).isoformat() if guest else None,
               "author": author or "", "guest": guest, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    DRAWINGS_DIR.mkdir(parents=True, exist_ok=True)
    drawing.save(DRAWINGS_DIR / f"{message['id']}.png")
    _render_to_file(message, width, height)
    with _lock:
        messages = _load()
        messages.append(message)
        _save(messages)
    push_priority(_path(message))
    if guest:
        _archive(message, _path(message))
    return message


def rerender_all(width, height):
    """Régénère toutes les images (par exemple pour un nouveau style de rendu)."""
    for m in list_messages():
        _render_to_file(m, width, height)


def ensure_images(width, height):
    """
    Régénère les images manquantes ou dont la taille ne correspond plus à l'écran
    (changement de résolution ou d'orientation, restauration d'une sauvegarde). Retourne le nombre d'images refaites.
    """
    from PIL import Image
    count = 0
    for m in list_messages():
        path = _path(m)
        try:
            with Image.open(path) as image:
                if image.size == (width, height):
                    continue
        except OSError:
            pass  # image absente ou illisible
        _render_to_file(m, width, height)
        count += 1
    return count


# --- Messages vocaux : enregistrés sur le téléphone, lus par le cadre quand leur carte s'affiche ---

VOICE_DIR = PROJECT_DIR / "cache" / "voice"
MAX_VOICE_SECONDS = 90
MAX_VOICE_BYTES = 15 * 1024 * 1024


def voice_path(message_id):
    return VOICE_DIR / f"{message_id}.ogg"


def render_voice_card(message, width, height):
    """Carte du message vocal : un micro, la durée et le prénom (le son est lu par le cadre)."""
    from PIL import ImageDraw
    from utils.message_renderer import _font, SANS_BOLD, SERIF_ITALIC
    image = render_message("", " ", "", "nuit", width, height).convert("RGB")
    draw = ImageDraw.Draw(image)
    cx, cy, unit = width / 2, height * 0.4, min(width, height) / 12
    accent = (255, 214, 120)
    draw.rounded_rectangle([cx - unit * 0.6, cy - unit * 1.5, cx + unit * 0.6, cy + unit * 0.4], radius=unit * 0.6, fill=accent)
    draw.arc([cx - unit, cy - unit * 0.9, cx + unit, cy + unit * 1.1], 0, 180, fill=accent, width=max(3, int(unit / 6)))
    draw.line([cx, cy + unit * 1.1, cx, cy + unit * 1.6], fill=accent, width=max(3, int(unit / 6)))
    for k, side in ((1, -1), (2, -1), (1, 1), (2, 1)):  # ondes sonores
        r = unit * (1.4 + 0.55 * k)
        start, end = (150, 210) if side < 0 else (-30, 30)
        draw.arc([cx - r, cy - r * 0.9, cx + r, cy + r * 0.9], start, end, fill=(200, 200, 230), width=max(2, int(unit / 10)))
    seconds = int(message.get("seconds") or 0)
    title = f"{message['signature']}" if message.get("signature") else ""
    big, small = _font(SANS_BOLD, int(height * 0.07)), _font(SERIF_ITALIC, int(height * 0.045))
    if title:
        draw.text((cx, height * 0.7), title, font=big, fill=(245, 245, 250), anchor="mm")
    draw.text((cx, height * 0.8), f"{seconds // 60}:{seconds % 60:02d}", font=small, fill=accent, anchor="mm")
    return image


def create_voice(data, signature, author, width, height, guest=True):
    """Enregistre un message vocal (converti en Ogg Vorbis, 90 s au plus) et sa carte dans le diaporama."""
    import subprocess
    import tempfile
    if not data or len(data) > MAX_VOICE_BYTES:
        raise ValueError("Enregistrement vide ou trop lourd.")
    message = {"id": secrets.token_hex(6), "kind": "voice", "title": "", "body": "", "signature": (signature or "").strip()[:MAX_SIGNATURE],
               "style": "nuit", "expires": (date.today() + timedelta(days=GUEST_MAX_DAYS)).isoformat() if guest else None,
               "author": author or "", "guest": guest, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".audio") as source:
        source.write(data)
        source.flush()
        for codec in (["-ac", "1", "-c:a", "libvorbis", "-q:a", "4"], ["-ac", "2", "-c:a", "vorbis", "-strict", "-2"]):  # repli : encodeur intégré
            result = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source.name, "-t", str(MAX_VOICE_SECONDS), "-vn", "-ar", "44100",
                                     "-af", "loudnorm=I=-16:TP=-1.5", *codec, str(voice_path(message["id"]))], capture_output=True, timeout=120)
            if result.returncode == 0 or b"Invalid data" in result.stderr:
                break
    if result.returncode != 0 or not voice_path(message["id"]).exists():
        voice_path(message["id"]).unlink(missing_ok=True)
        raise ValueError("Ce fichier n'est pas un enregistrement audio lisible.")
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(voice_path(message["id"]))],
                             capture_output=True, text=True, timeout=30).stdout
        message["seconds"] = round(float(out.strip()))
    except (ValueError, OSError):
        message["seconds"] = 0
    if message["seconds"] < 1:
        voice_path(message["id"]).unlink(missing_ok=True)
        raise ValueError("Enregistrement trop court.")
    _render_to_file(message, width, height)
    with _lock:
        messages = _load()
        messages.append(message)
        _save(messages)
    push_priority(_path(message))
    if guest:
        _archive(message, _path(message))
    return message
