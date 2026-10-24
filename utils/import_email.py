"""
Envoi par e-mail : le cadre relève une boîte mail (IMAP, par ex. une adresse Gmail créée pour lui, avec un mot de
passe d'application) et affiche les photos et vidéos jointes. Les expéditeurs autorisés arrivent directement sur
le cadre (source « email ») ; les autres attendent la validation, comme les photos d'invités, ou sont ignorés.
L'objet du message (ou sa première ligne) devient la légende.
"""
import email
import email.policy
import imaplib
import json
import re
import secrets
import threading
import time
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

TARGET_DIR = Path("static/photos/email")
PENDING_DIR = Path("static/pending_uploads")
STATE_FILE = Path("cache") / "email_state.json"
CAPTIONS_FILE = Path("cache") / "email_captions.json"
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".mp4", ".mov"}
MAX_PER_RUN = 50
TIMEOUT = 30
_lock = threading.Lock()


def _load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def captions():
    """Légendes des photos reçues par e-mail ({nom de fichier: légende}), utilisées à la préparation."""
    return _load_json(CAPTIONS_FILE, {})


def allowed(config):
    """Adresses autorisées (en minuscules)."""
    return {a.strip().lower() for a in config.get("email_allowed_senders") or [] if "@" in a}


def connect(config):
    host = str(config.get("email_imap_host") or "").strip()
    user = str(config.get("email_user") or "").strip()
    if not host or not user or not config.get("email_password"):
        raise ValueError("Renseignez le serveur IMAP, l'adresse et le mot de passe.")
    port = int(config.get("email_imap_port") or 993)
    box = imaplib.IMAP4_SSL(host, port, timeout=TIMEOUT)
    try:
        box.login(user, config["email_password"])
    except imaplib.IMAP4.error:
        box.logout()
        raise ValueError("Connexion refusée : vérifiez l'adresse et le mot de passe (pour Gmail : un mot de passe d'application).")
    return box


def test(config):
    """Vérifie la connexion ; renvoie le nombre de messages de la boîte."""
    box = connect(config)
    try:
        status, data = box.select(config.get("email_folder") or "INBOX", readonly=True)
        if status != "OK":
            raise ValueError("Dossier introuvable dans la boîte mail.")
        return int(data[0] or 0)
    finally:
        box.logout()


def _caption(message):
    subject = str(message.get("Subject") or "").strip()
    if re.match(r"^(re|tr|fwd?|wg)\s*:", subject, re.I):
        subject = re.sub(r"^((re|tr|fwd?|wg)\s*:\s*)+", "", subject, flags=re.I)
    if subject:
        return subject[:200]
    body = message.get_body(preferencelist=("plain",))
    if body is not None:
        try:
            for line in body.get_content().splitlines():
                line = line.strip()
                if line and not line.startswith(">") and not line.startswith("--"):
                    return line[:200]
        except (LookupError, ValueError):
            pass
    return ""


def attachments(message):
    """Photos et vidéos jointes : [(nom, contenu)]."""
    found = []
    for part in message.iter_attachments() if message.is_multipart() else []:
        name = part.get_filename() or ""
        ext = Path(name).suffix.lower()
        if ext not in MEDIA_EXT and part.get_content_maintype() == "image":
            ext = "." + (part.get_content_subtype().replace("jpeg", "jpg"))
        if ext not in MEDIA_EXT:
            continue
        data = part.get_payload(decode=True)
        if data:
            found.append((Path(name).stem or "photo", ext, data))
    return found


def _safe(stem):
    return re.sub(r"[^A-Za-z0-9_-]", "_", stem)[:60] or "photo"


def handle(message, config):
    """Range les pièces jointes d'un message : {"accepted": n, "pending": n, "ignored": n}."""
    sender = parseaddr(str(message.get("From") or ""))[1].lower()
    trusted = sender in allowed(config)
    policy = config.get("email_unknown_senders", "pending")  # pending | ignore
    files = attachments(message)
    result = {"accepted": 0, "pending": 0, "ignored": 0, "sender": sender}
    if not files:
        return result
    if not trusted and policy != "pending":
        result["ignored"] = len(files)
        return result
    try:
        when = parsedate_to_datetime(message.get("Date"))
    except (TypeError, ValueError):
        when = None
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    caption = _caption(message)
    caption_map = captions() if trusted else None
    folder = TARGET_DIR if trusted else PENDING_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for stem, ext, data in files:
        name = f"{stamp}_{_safe(stem)}_{secrets.token_hex(2)}{ext}"
        (folder / name).write_bytes(data)
        if trusted:
            result["accepted"] += 1
            if caption:
                caption_map[name] = caption
        else:
            result["pending"] += 1
    if caption_map is not None:
        _save_json(CAPTIONS_FILE, caption_map)
    return result


def check(config):
    """Relève les nouveaux messages (depuis la dernière relève) : {"accepted", "pending", "ignored"}."""
    if not _lock.acquire(blocking=False):
        return {"accepted": 0, "pending": 0, "ignored": 0, "busy": True}
    try:
        return _check(config)
    finally:
        _lock.release()


def _check(config):
    totals = {"accepted": 0, "pending": 0, "ignored": 0}
    box = connect(config)
    try:
        status, _data = box.select(config.get("email_folder") or "INBOX")
        if status != "OK":
            raise ValueError("Dossier introuvable dans la boîte mail.")
        validity = box.response("UIDVALIDITY")[1][0]
        validity = validity.decode() if isinstance(validity, bytes) else str(validity)
        state = _load_json(STATE_FILE, {})
        if state.get("validity") != validity:
            # Première relève (ou boîte recréée) : on part de maintenant, sans importer tout l'historique
            status, data = box.uid("search", None, "ALL")
            uids = [int(u) for u in (data[0] or b"").split()] if status == "OK" else []
            _save_json(STATE_FILE, {"validity": validity, "last_uid": max(uids) if uids else 0, "since": time.time()})
            return totals
        last = int(state.get("last_uid", 0))
        status, data = box.uid("search", None, f"UID {last + 1}:*")
        uids = sorted(u for u in (int(x) for x in (data[0] or b"").split()) if u > last) if status == "OK" else []
        for uid in uids[:MAX_PER_RUN]:
            status, parts = box.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple)), None) if status == "OK" else None
            if raw:
                result = handle(email.message_from_bytes(raw, policy=email.policy.default), config)
                for key in totals:
                    totals[key] += result[key]
            last = uid
            state.update(last_uid=last)
            _save_json(STATE_FILE, state)
        return totals
    finally:
        try:
            box.logout()
        except Exception:
            pass
