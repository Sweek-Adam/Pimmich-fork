"""
Sauvegarde complète, restaurable en un clic : réglages, comptes, playlists, messages (dessins et vocaux compris),
livre d'or, légendes, réactions, statistiques, historique… et, sur option, les photos d'origine
(alors enregistrée sur un disque USB ou un NAS : c'est trop gros pour un téléchargement).

À la restauration, seuls les emplacements prévus ci-dessous sont écrits (jamais un chemin arbitraire du zip).
"""
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
MARKER = "pimmich_full_backup.json"
# Dossiers et fichiers sauvegardés (relatifs au projet)
INCLUDED = ["config", "cache/drawings", "cache/voice", "cache/caption_styles.json", "cache/icloud_captions.json",
            "cache/whatsapp_captions.json", "cache/email_captions.json", "cache/reactions.json", "cache/view_counts.json",
            "cache/history.json", "cache/people.json", "cache/beats.json", "static/guestbook", "static/music",
            "static/prepared/messages", "static/messages_hidden"]
PHOTOS = "static/photos"
SKIP_NAMES = {".update_state.json", "secret_key", "internal_token"}  # propres à l'installation


def _files(relative, photos=False):
    root = PROJECT_DIR / relative
    if root.is_file():
        yield root
        return
    for dirpath, _dirs, names in os.walk(root, followlinks=photos):
        for name in names:
            if name in SKIP_NAMES or name.endswith((".tmp", ".part")):
                continue
            yield Path(dirpath) / name


def _allowed(name, photos=False):
    """Un nom du zip est-il un emplacement prévu (et sûr) ?"""
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or name == MARKER:
        return False
    prefixes = INCLUDED + ([PHOTOS] if photos else [])
    return any(name == p or name.startswith(p.rstrip("/") + "/") for p in prefixes)


def build(target, with_photos=False, progress=lambda done, total: None):
    """Écrit l'archive dans `target` ; renvoie (nombre de fichiers, octets)."""
    sources = [p for rel in INCLUDED for p in _files(rel)]
    if with_photos:
        sources += list(_files(PHOTOS, photos=True))
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".part")
    total = len(sources)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.writestr(MARKER, json.dumps({"created": datetime.now().isoformat(timespec="seconds"), "photos": with_photos, "files": total}))
        for done, path in enumerate(sources, 1):
            name = str(path.relative_to(PROJECT_DIR))  # chemin vu depuis le projet (même pour une source sur un autre support)
            compress = zipfile.ZIP_STORED if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov", ".mp3", ".ogg") else zipfile.ZIP_DEFLATED
            try:
                zf.write(path, name, compress_type=compress)
            except OSError:
                continue
            if done % 50 == 0 or done == total:
                progress(done, total)
    tmp.replace(target)
    return total, target.stat().st_size


def info(path):
    try:
        with zipfile.ZipFile(path) as zf:
            return json.loads(zf.read(MARKER))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def restore(path):
    """Restaure une sauvegarde complète ; renvoie le nombre de fichiers écrits."""
    meta = info(path)
    if meta is None:
        raise ValueError("Ce fichier n'est pas une sauvegarde complète de Pimmich.")
    written = 0
    with zipfile.ZipFile(path) as zf:
        for member in zf.infolist():
            if member.is_dir() or not _allowed(member.filename, photos=bool(meta.get("photos"))):
                continue
            target = PROJECT_DIR / member.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.restore")
            with zf.open(member) as source, open(tmp, "wb") as out:
                while True:
                    chunk = source.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            if target.name in ("users.json", "gdrive_service_account.json"):
                tmp.chmod(0o600)
            tmp.replace(target)
            written += 1
    return written
