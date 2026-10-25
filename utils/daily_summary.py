"""
Bilan du jour (notification facultative, à l'heure choisie) : photos et vidéos reçues, messages des invités,
médias en échec, place libre, température et alimentation du Raspberry Pi.
"""
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from utils.message_renderer import N_

STATE_FILE = Path("cache") / "daily_summary.json"
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp")
VIDEO_EXT = (".mp4", ".mov", ".avi", ".mkv", ".m4v")


def _received(since, root=Path("static") / "photos"):
    photos = videos = 0
    for folder in root.iterdir() if root.is_dir() else []:
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        for entry in os.scandir(folder):
            if not entry.is_file() or entry.name.startswith("."):
                continue
            try:
                if entry.stat().st_mtime < since:
                    continue
            except OSError:
                continue
            lower = entry.name.lower()
            if lower.endswith(VIDEO_EXT):
                videos += 1
            elif lower.endswith(PHOTO_EXT):
                photos += 1
    return photos, videos


def build(config, now=None, translate=lambda s, **k: s % k if k else s):
    """(titre, texte) du bilan des dernières 24 heures."""
    from utils import hardware
    from utils import prepare_all_photos as prep
    now = now or time.time()
    lines = []
    photos, videos = _received(now - 86400)
    lines.append(translate(N_("Reçus : %(photos)s photo(s), %(videos)s vidéo(s)."), photos=photos, videos=videos))
    try:
        from utils import messages_manager
        today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        messages = sum(1 for m in messages_manager.list_messages() if str(m.get("created", "")).startswith(today) and m.get("guest"))
        if messages:
            lines.append(translate(N_("Messages des invités : %(count)s."), count=messages))
    except Exception:
        pass
    failed = len(prep.preparation_errors())
    if failed:
        lines.append(translate(N_("Médias en échec : %(count)s (voir Préparation des médias)."), count=failed))
    try:
        free = shutil.disk_usage("/").free / 1024 ** 3
        lines.append(translate(N_("Place libre : %(size)s Go."), size=f"{free:.1f}"))
    except OSError:
        pass
    temp = hardware.temperature()
    if temp is not None:
        lines.append(translate(N_("Température : %(temp)s °C."), temp=round(temp)))
    flags = hardware.throttled()
    if flags is not None and flags & hardware.UNDERVOLT_SINCE_BOOT:
        lines.append(translate(N_("Attention : l'alimentation a faibli depuis le démarrage.")))
    return translate(N_("Bilan du jour")), "\n".join(lines)


def due(config, now=None):
    """Faut-il envoyer le bilan maintenant ? (une fois par jour, à partir de l'heure choisie)"""
    now = datetime.fromtimestamp(now or time.time())
    try:
        hour, minute = (int(v) for v in str(config.get("daily_summary_time", "20:00")).split(":"))
    except ValueError:
        hour, minute = 20, 0
    if (now.hour, now.minute) < (hour, minute):
        return False
    try:
        sent = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("sent")
    except (OSError, ValueError):
        sent = None
    return sent != now.strftime("%Y-%m-%d")


def mark_sent(now=None):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"sent": datetime.fromtimestamp(now or time.time()).strftime("%Y-%m-%d")}), encoding="utf-8")
