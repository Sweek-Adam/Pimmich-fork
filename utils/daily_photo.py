"""
Photo du jour par e-mail : chaque jour, à l'heure choisie, les proches qui n'ont pas de cadre reçoivent une photo.

- Envoi depuis la boîte mail du cadre (la même que pour recevoir des photos : adresse et mot de passe d'application),
  par SMTP ; le serveur d'envoi est déduit du serveur IMAP (imap.gmail.com -> smtp.gmail.com) s'il n'est pas donné.
- Choix de la photo : un souvenir « ce jour-là, il y a N ans » d'abord, sinon une photo arrivée ces derniers jours,
  sinon une des plus aimées ou des favorites ; jamais une photo déjà envoyée ces 60 derniers jours.
- Désactivé par défaut ; seuls les destinataires saisis reçoivent la photo.
"""
import io
import json
import random
import smtplib
import time
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_DIR / "cache" / "daily_photo.json"
NO_REPEAT_DAYS = 60
RECENT_DAYS = 3
MAX_SIDE = 1600
TIMEOUT = 30


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def recipients(config):
    return [a for a in config.get("daily_photo_recipients") or [] if "@" in a][:30]


def due(config, state, now=None):
    """Vrai à l'heure choisie (ou après), une seule fois par jour."""
    if not config.get("daily_photo_enabled") or not recipients(config):
        return False
    now = now or datetime.now()
    try:
        hour, minute = (int(x) for x in str(config.get("daily_photo_time") or "08:00").split(":", 1))
    except ValueError:
        hour, minute = 8, 0
    return state.get("last_day") != now.strftime("%Y-%m-%d") and (now.hour, now.minute) >= (hour, minute)


def pick(index, today=None, loved=None, favorites=(), recent_files=(), sent=None, rng=None):
    """Photo du jour : (clé, raison, années) ; raison : « memory », « new » ou « loved ». None si rien ne convient."""
    today, rng, loved, sent = today or date.today(), rng or random.Random(), loved or {}, sent or {}
    cutoff = time.time() - NO_REPEAT_DAYS * 86400
    fresh = lambda key: sent.get(key, 0) < cutoff and key.split("/", 1)[0] != "messages"  # noqa: E731
    memories = []
    for key, entry in index.items():
        try:
            when = datetime.fromisoformat(entry["date"]) if entry.get("date") else None
        except ValueError:
            continue
        if when and when.month == today.month and when.day == today.day and when.year < today.year and fresh(key) \
                and not (entry.get("q") or {}).get("shot"):
            memories.append((loved.get(key, 0), today.year - when.year, key))
    if memories:
        _score, years, key = max(memories, key=lambda m: (m[0], rng.random()))
        return key, "memory", years
    new = [k for k in recent_files if fresh(k)]
    if new:
        return rng.choice(new), "new", 0
    best = [k for k, n in sorted(loved.items(), key=lambda i: -i[1]) if fresh(k)][:20] + [k for k in favorites if fresh(k)]
    if best:
        return rng.choice(best), "loved", 0
    others = [k for k, e in index.items() if fresh(k) and not (e.get("q") or {}).get("shot")]
    return (rng.choice(others), "loved", 0) if others else None


def smtp_host(config):
    host = str(config.get("email_smtp_host") or "").strip()
    if host:
        return host
    imap = str(config.get("email_imap_host") or "").strip()
    if imap.startswith("imap."):
        return "smtp." + imap[5:]
    return {"outlook.office365.com": "smtp.office365.com"}.get(imap, imap)


def jpeg(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def message(config, to, subject, text, html, image_bytes):
    mail = EmailMessage()
    mail["From"] = config.get("email_user")
    mail["To"] = config.get("email_user")
    mail["Bcc"] = ", ".join(to)  # les proches ne voient pas les adresses des autres
    mail["Subject"] = subject
    mail.set_content(text)
    mail.add_alternative(html.replace("{cid}", "photo"), subtype="html")
    mail.get_payload()[1].add_related(image_bytes, "image", "jpeg", cid="<photo>", filename="photo.jpg")
    return mail


def send(config, mail):
    host, port = smtp_host(config), int(config.get("email_smtp_port") or 465)
    if not host or not config.get("email_user") or not config.get("email_password"):
        raise ValueError("Configurez d'abord la boîte mail du cadre (Sources › E-mail).")
    if port == 587:
        with smtplib.SMTP(host, port, timeout=TIMEOUT) as server:
            server.starttls()
            server.login(config["email_user"], config["email_password"])
            server.send_message(mail)
    else:
        with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT) as server:
            server.login(config["email_user"], config["email_password"])
            server.send_message(mail)
