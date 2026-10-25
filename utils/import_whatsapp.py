"""
Import WhatsApp : WhatsApp n'offre aucun accès aux discussions, mais « Exporter la discussion » (avec les médias)
produit un .zip contenant les photos, les vidéos et le texte de la discussion. Pimmich en tire les photos et vidéos,
leur date exacte, l'expéditeur et le message qui les accompagne (légende), et les range dans la source « whatsapp ».

Le format du texte varie selon le téléphone et la langue :
  iPhone  : [12/08/2025, 14:03:21] Mamie: <attaché : 00000012-PHOTO-2025-08-12-14-03-21.jpg>
  Android : 12/08/2025 14:03 - Mamie: IMG-20250812-WA0003.jpg (fichier joint)
            La mer était bonne !
On reconnaît donc les médias par leur nom de fichier (présent dans le .zip), pas par les mots qui l'entourent.
"""
import hashlib
import json
import re
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from utils.platform_info import tmp_path

TARGET_DIR = Path("static/photos/whatsapp")
UPLOAD_FILE = Path("cache") / "whatsapp_upload.zip"
CAPTIONS_FILE = Path("cache") / "whatsapp_captions.json"
MANIFEST_FILE = TARGET_DIR / ".whatsapp_manifest.json"
CANCEL_FLAG = tmp_path("pimmich_cancel_import.flag")
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".mp4", ".mov"}
CAPTION_MODES = ("text", "sender", "both", "none")
MAX_CHAT_BYTES = 50 * 1024 * 1024
_lock = threading.Lock()

# [date, heure] Nom: texte (iPhone) — ou — date heure - Nom: texte (Android)
LINE = re.compile(r"^‎?\[?(?P<date>\d{1,4}[./-]\d{1,2}[./-]\d{1,4}),?\s+(?P<time>\d{1,2}[:.]\d{2}(?:[:.]\d{2})?)"
                  r"(?:\s?(?P<ampm>[AaPp]\.?\s?[Mm]\.?))?\]?\s*(?:-\s)?(?P<sender>[^:‎]{1,80}):\s(?P<text>.*)$")


def _is_media(name):
    path = Path(name)
    stem = path.stem.upper()
    return (path.suffix.lower() in MEDIA_EXT and not path.name.startswith(".") and "__MACOSX" not in name
            and "STICKER" not in stem)


def _chat_member(archive):
    """Le fichier texte de la discussion (_chat.txt sur iPhone, « Discussion WhatsApp avec ….txt » sur Android)."""
    texts = [i for i in archive.infolist() if i.filename.lower().endswith(".txt") and "__MACOSX" not in i.filename]
    texts.sort(key=lambda i: (Path(i.filename).name != "_chat.txt", -i.file_size))
    return texts[0] if texts else None


def _day_first(dates):
    """Ordre jour/mois de l'export : on cherche une date sans ambiguïté (13/08 = jour d'abord)."""
    for raw in dates:
        parts = re.split(r"[./-]", raw)
        if len(parts[0]) == 4:
            continue
        if int(parts[0]) > 12:
            return True
        if int(parts[1]) > 12:
            return False
    return True  # par défaut : jour/mois (Europe)


def _when(raw_date, raw_time, ampm, day_first):
    parts = [int(p) for p in re.split(r"[./-]", raw_date)]
    if raw_date[:4].isdigit() and len(re.split(r"[./-]", raw_date)[0]) == 4:
        year, month, day = parts
    else:
        day, month, year = parts if day_first else (parts[1], parts[0], parts[2])
    if year < 100:
        year += 2000
    clock = [int(p) for p in re.split(r"[:.]", raw_time)] + [0]
    hour, minute, second = clock[0], clock[1], clock[2]
    if ampm:
        pm = ampm.strip().lower().startswith("p")
        hour = hour % 12 + (12 if pm else 0)
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def _clean_caption(text, name):
    """Retire le nom du fichier et la mention « fichier joint » (dans toutes les langues) du message."""
    escaped = re.escape(name)
    text = re.sub(r"<[^<>]*" + escaped + r"[^<>]*>", "", text)
    text = re.sub(escaped + r"\s*\([^()]*\)", "", text)
    text = text.replace(name, "")
    return re.sub(r"\s+", " ", text.replace("‎", "")).strip(" :-")


def parse(archive):
    """Analyse d'un export : {media: {nom: {sender, date, caption}}, senders: {nom: nombre}, first, last}."""
    media_names = {Path(i.filename).name: i.filename for i in archive.infolist() if _is_media(i.filename)}
    messages = []
    member = _chat_member(archive)
    if member is not None and member.file_size <= MAX_CHAT_BYTES:
        text = archive.read(member).decode("utf-8-sig", errors="replace")
        for line in text.splitlines():
            match = LINE.match(line)
            if match:
                messages.append(dict(match.groupdict()))
            elif messages:  # suite du message précédent (légende sur la ligne suivante, Android)
                messages[-1]["text"] += "\n" + line
    day_first = _day_first(m["date"] for m in messages)
    media = {}
    for message in messages:
        found = [name for name in media_names if name in message["text"]]
        if not found:
            continue
        when = _when(message["date"], message["time"], message.get("ampm"), day_first)
        sender = message["sender"].strip()
        for name in found:
            caption = _clean_caption(message["text"], name)
            for other in found:
                caption = _clean_caption(caption, other)
            media[name] = {"sender": sender, "date": when.isoformat() if when else None, "caption": caption[:300]}
    for name in media_names:  # médias absents du texte (export partiel) : importés quand même
        media.setdefault(name, {"sender": "", "date": None, "caption": ""})
    senders = {}
    for info in media.values():
        if info["sender"]:
            senders[info["sender"]] = senders.get(info["sender"], 0) + 1
    dates = sorted(i["date"] for i in media.values() if i["date"])
    return {"media": media, "paths": media_names, "senders": senders,
            "first": dates[0] if dates else None, "last": dates[-1] if dates else None}


def analyse(zip_path):
    """Résumé d'un export pour l'interface : nombre de photos/vidéos, période, expéditeurs."""
    with zipfile.ZipFile(zip_path) as archive:
        info = parse(archive)
    videos = sum(1 for n in info["media"] if Path(n).suffix.lower() in (".mp4", ".mov"))
    return {"photos": len(info["media"]) - videos, "videos": videos, "first": info["first"], "last": info["last"],
            "senders": sorted(({"name": k, "count": v} for k, v in info["senders"].items()), key=lambda s: -s["count"])}


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
    """Légendes des médias WhatsApp ({nom de fichier: légende}), utilisées à la préparation."""
    return _load_json(CAPTIONS_FILE, {})


def _caption(info, mode):
    text, sender = info["caption"], info["sender"].split(" ")[0] if info["sender"] else ""
    if mode == "text":
        return text
    if mode == "sender":
        return sender
    if mode == "both":
        return f"{sender} : {text}" if sender and text else sender or text
    return ""


def _local_name(name, info):
    """Nom local : la date exacte en tête (WhatsApp efface la date des photos), puis le nom d'origine."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:120]
    if info["date"]:
        stamp = datetime.fromisoformat(info["date"]).strftime("%Y%m%d_%H%M%S")
        if stamp[:8] not in safe.replace("-", ""):
            return f"{stamp}_{safe}"
    return safe


def import_export(zip_path, senders=None, caption_mode="text"):
    """Importe les photos et vidéos d'un export (expéditeurs choisis ; tous si None). Les doublons sont ignorés."""
    if not _lock.acquire(blocking=False):
        yield {"type": "error", "message": "Un import WhatsApp est déjà en cours."}
        return
    try:
        yield from _import(zip_path, set(senders) if senders else None, caption_mode if caption_mode in CAPTION_MODES else "text")
    finally:
        _lock.release()


def _import(zip_path, senders, caption_mode):
    try:
        archive = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile):
        yield {"type": "error", "message": "Ce fichier n'est pas un export WhatsApp (.zip)."}
        return
    with archive:
        info = parse(archive)
        chosen = [n for n, i in info["media"].items() if senders is None or i["sender"] in senders]
        if not chosen:
            yield {"type": "error", "message": "Aucune photo ni vidéo dans cet export (pensez à « Joindre les médias »)."}
            return
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        manifest = _load_json(MANIFEST_FILE, {})  # empreinte -> nom local
        caption_map = captions()
        total, added = len(chosen), 0
        yield {"type": "stats", "stage": "COPYING", "percent": 10, "message": f"Import de {total} médias WhatsApp...", "total": total}
        for index, name in enumerate(sorted(chosen), 1):
            if CANCEL_FLAG.exists():
                yield {"type": "warning", "message": "Import annulé par l'utilisateur."}
                break
            part = TARGET_DIR / ".whatsapp.part"
            digest = hashlib.sha1()
            with archive.open(info["paths"][name]) as source, open(part, "wb") as out:  # par morceaux : vidéos lourdes
                for chunk in iter(lambda: source.read(1 << 20), b""):
                    digest.update(chunk)
                    out.write(chunk)
            digest = digest.hexdigest()
            if digest not in manifest or not (TARGET_DIR / manifest[digest]).is_file():
                local = _local_name(name, info["media"][name])
                part.replace(TARGET_DIR / local)
                manifest[digest] = local
                added += 1
            part.unlink(missing_ok=True)
            local = manifest[digest]
            caption = _caption(info["media"][name], caption_mode)
            if caption:
                caption_map[local] = caption
            yield {"type": "progress", "stage": "COPYING", "percent": 10 + int(index / total * 70),
                   "message": f"Import... ({index}/{total})", "current": index, "total": total}
    _save_json(MANIFEST_FILE, manifest)
    _save_json(CAPTIONS_FILE, caption_map)
    yield {"type": "done", "stage": "IMPORT_COMPLETE", "percent": 80, "changes": added, "total_imported": added,
           "message": f"WhatsApp : {added} nouveaux médias ({total - added} déjà présents)."}
