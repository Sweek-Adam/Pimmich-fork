"""
Gagner de la place : les originaux énormes déjà préparés (photos de 50 Mpx et plus, vidéos 4K...) peuvent être
remplacés par une version réduite qui reste bien plus grande que l'écran :
  - photos JPEG : 4096 px au plus grand côté, qualité 88, données EXIF gardées (date, GPS, orientation) ;
  - vidéos MP4 / MOV : 1080p, H.264, son AAC ; la nuit seulement (long sur un Raspberry Pi).
Le nom et la date du fichier ne changent pas : la préparation, les visages, les doublons et les synchronisations
(Google Drive, iCloud : suivis par leur manifeste) continuent comme avant.
Pour les sources sans autre copie (téléphone, invités, Telegram, clé USB...), l'original réduit est le seul
exemplaire : l'interface le signale avant de réduire.
"""
import json
import os
import subprocess
import threading
import time
import warnings
from pathlib import Path

from PIL import Image

from utils import busy

PHOTO_MAX_SIDE = 4096
PHOTO_MIN_BYTES = 4 * 1024 * 1024
VIDEO_MAX_HEIGHT = 1080
VIDEO_MIN_BYTES = 100 * 1024 * 1024
VIDEO_TARGET_BPS = 6_500_000           # 1080p H.264 CRF 23 : environ 6 Mbit/s, son compris
PHOTO_EXT = (".jpg", ".jpeg")
VIDEO_EXT = (".mp4", ".mov", ".m4v")
CLOUD_SOURCES = {"gdrive", "cloud", "immich", "icloud", "samba", "personnes"}  # l'original existe ailleurs
REGISTRY = Path("cache") / "space_saver.json"     # médias réduits, vidéos en attente, mesures des vidéos
_lock = threading.RLock()


def _load():
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("reduced", {})
    data.setdefault("queue", [])
    data.setdefault("probe", {})
    return data


def _save(data):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, REGISTRY)


def _probe_video(path, cache):
    """(hauteur, durée en s) d'une vidéo, mémorisés selon le poids et la date du fichier."""
    stat = path.stat()
    key = f"{path}:{stat.st_size}:{int(stat.st_mtime)}"
    if key in cache:
        return tuple(cache[key])
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height:format=duration",
                              "-of", "json", str(path)], capture_output=True, text=True, timeout=60).stdout
        info = json.loads(out or "{}")
        height = int((info.get("streams") or [{}])[0].get("height") or 0)
        duration = float((info.get("format") or {}).get("duration") or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        height, duration = 0, 0.0
    cache[key] = [height, duration]
    return height, duration


def candidates(width, height, sources=None):
    """Originaux déjà préparés qui gagneraient beaucoup à être réduits, du plus gros gain au plus petit."""
    from utils import prepare_all_photos as prep
    root = Path("static") / "photos"
    found = []
    with _lock:
        data = _load()
        queued = {(q["source"], q["name"]) for q in data["queue"]}
        for source in sources or sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")) if root.is_dir() else []:
            folder = root / source
            prepared = Path("static") / "prepared" / source
            for entry in os.scandir(folder) if folder.is_dir() else []:
                name, lower = entry.name, entry.name.lower()
                if not entry.is_file() or name.startswith(".") or not lower.endswith(PHOTO_EXT + VIDEO_EXT):
                    continue
                size = entry.stat().st_size
                done = data["reduced"].get(f"{source}/{name}")
                if done and done.get("after") == size:
                    continue  # déjà réduit
                if prep.preparation_state(prepared, name, width, height) != "ok":
                    continue  # jamais avant que le média soit prêt sur le cadre
                path = Path(entry.path)
                if lower.endswith(PHOTO_EXT):
                    if size < PHOTO_MIN_BYTES:
                        continue
                    try:
                        with warnings.catch_warnings():  # photos géantes attendues ici (lecture de l'en-tête seulement)
                            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                            image = Image.open(path)
                        with image:
                            w, h = image.size
                    except Exception:
                        continue
                    if max(w, h) <= PHOTO_MAX_SIDE * 1.15:
                        continue
                    scale = PHOTO_MAX_SIDE / max(w, h)
                    estimate = int(size * scale * scale * 1.1)
                    kind, detail = "photo", f"{w}×{h}"
                else:
                    if size < VIDEO_MIN_BYTES:
                        continue
                    video_height, duration = _probe_video(path, data["probe"])
                    if not duration:
                        continue
                    estimate = int(duration * VIDEO_TARGET_BPS / 8)
                    if video_height and video_height <= VIDEO_MAX_HEIGHT and estimate > size * 0.6:
                        continue  # déjà en 1080p et pas trop lourde : peu à gagner
                    kind, detail = "video", f"{video_height}p · {int(duration // 60)} min {int(duration % 60):02d}"
                if estimate >= size * 0.8:
                    continue
                found.append({"source": source, "name": name, "kind": kind, "size": size, "estimate": estimate, "detail": detail,
                              "gain": size - estimate, "cloud_copy": source in CLOUD_SOURCES, "queued": (source, name) in queued})
        try:
            _save(data)  # mesures des vidéos gardées : la page s'ouvre vite la fois suivante
        except OSError:
            pass
    return sorted(found, key=lambda c: -c["gain"])


def summary():
    with _lock:
        data = _load()
    saved = sum(max(0, r.get("before", 0) - r.get("after", 0)) for r in data["reduced"].values())
    return {"saved": saved, "count": len(data["reduced"]), "queue": list(data["queue"])}


def _remember(source, name, before, after):
    with _lock:
        data = _load()
        data["reduced"][f"{source}/{name}"] = {"before": before, "after": after, "at": time.strftime("%Y-%m-%d %H:%M")}
        data["queue"] = [q for q in data["queue"] if (q["source"], q["name"]) != (source, name)]
        _save(data)


def reduce_photo(path):
    """Réduit une photo JPEG sur place (même nom, même date). Retourne (avant, après) en octets."""
    path = Path(path)
    before, stat = path.stat().st_size, path.stat()
    tmp = path.with_name(f".{path.name}.reduction")
    with warnings.catch_warnings():  # décodée directement réduite (JPEG) : pas de risque mémoire
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        image = Image.open(path)
    with image:
        exif, icc = image.info.get("exif"), image.info.get("icc_profile")
        image.draft("RGB", (PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
        image = image.convert("RGB")
        image.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE), Image.LANCZOS)  # pixels tels qu'enregistrés : l'orientation EXIF reste juste
        options = {"quality": 88, "optimize": True}
        if exif:
            options["exif"] = exif
        if icc:
            options["icc_profile"] = icc
        image.save(tmp, "JPEG", **options)
    after = tmp.stat().st_size
    if after >= before:
        tmp.unlink(missing_ok=True)
        return before, before
    os.utime(tmp, (stat.st_atime, stat.st_mtime))
    os.replace(tmp, path)
    return before, after


def reduce_video(path, runner=None):
    """Réencode une vidéo sur place en 1080p (même nom, même conteneur, même date). Retourne (avant, après)."""
    from utils import prepare_all_photos as prep
    path = Path(path)
    stat = path.stat()
    before = stat.st_size
    tmp = path.with_name(f".{path.stem}.reduction{path.suffix}")
    command = ["nice", "-n", "15", "ffmpeg", "-y", "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0",
               "-vf", f"scale=-2:'min({VIDEO_MAX_HEIGHT},ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)]
    code, errors = (runner or prep.run_ffmpeg)(command)
    if code != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg a échoué ({code}) : {errors.strip()[-300:]}")
    after = tmp.stat().st_size
    if after >= before:
        tmp.unlink(missing_ok=True)
        return before, before
    os.utime(tmp, (stat.st_atime, stat.st_mtime))
    os.replace(tmp, path)
    return before, after


def request(items, now_ok_for_videos):
    """
    Réduit les photos tout de suite ; les vidéos aussi si c'est la nuit, sinon elles attendent la nuit.
    `items` : [(source, nom)] validés par l'appelant. Retourne {"photos": n, "videos_now": [...], "videos_later": n, "saved": octets}.
    """
    from utils import prepare_all_photos as prep
    result = {"photos": 0, "videos_now": [], "videos_later": 0, "saved": 0, "errors": []}
    for source, name in items:
        path = Path("static") / "photos" / source / name
        if name.lower().endswith(PHOTO_EXT):
            try:
                with prep.PREPARE_LOCK, busy.working(f"réduction de {source}/{name}"):
                    before, after = reduce_photo(path)
                _remember(source, name, before, after)
                result["photos"] += 1
                result["saved"] += before - after
            except Exception as e:
                result["errors"].append(f"{name} : {e}")
        elif now_ok_for_videos:
            result["videos_now"].append((source, name))
        else:
            with _lock:
                data = _load()
                if not any((q["source"], q["name"]) == (source, name) for q in data["queue"]):
                    data["queue"].append({"source": source, "name": name})
                _save(data)
            result["videos_later"] += 1
    return result


def run_videos(items, still_night=lambda: True):
    """Réduit des vidéos (la nuit, une à la fois). Retourne les octets gagnés."""
    from utils import prepare_all_photos as prep
    saved = 0
    for source, name in items:
        if not still_night():
            break
        path = Path("static") / "photos" / source / name
        if not path.is_file():
            _remember(source, name, 0, 0)
            continue
        try:
            with prep.PREPARE_LOCK, busy.working(f"réduction de {source}/{name}"):
                before, after = reduce_video(path)
            _remember(source, name, before, after)
            saved += before - after
        except Exception as e:
            with _lock:  # on ne réessaie pas chaque nuit une vidéo que ffmpeg refuse
                data = _load()
                data["queue"] = [q for q in data["queue"] if (q["source"], q["name"]) != (source, name)]
                data["reduced"][f"{source}/{name}"] = {"before": path.stat().st_size, "after": path.stat().st_size, "error": str(e)[:200]}
                _save(data)
    return saved


def queued():
    with _lock:
        return [(q["source"], q["name"]) for q in _load()["queue"]]
