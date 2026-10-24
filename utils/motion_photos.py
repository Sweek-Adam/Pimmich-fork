"""
Photos animées des téléphones, rejouées sur le cadre comme les GIF (utils/animated.py) :
  - Samsung « Photo animée » et Google « Photo animée / Motion Photo » : une courte vidéo MP4 rangée dans le JPEG ;
  - iPhone « Live Photo » : la photo (HEIC ou JPEG) et une courte vidéo .MOV du même nom.
La photo reste préparée comme d'habitude ; la nuit (travail lourd), une animation WebP de quelques secondes est
créée au cadrage exact de la photo, puis rejouée par-dessus en photo seule et dans les dispositions.
"""
import json
import os
import struct
import subprocess
from pathlib import Path

CACHE_DIR = Path("cache") / "motion"     # clips extraits et animations (jamais dans les dossiers synchronisés)
MAX_SECONDS = 4
FPS = 15
MAX_SIDE = 960
LIVE_PHOTO_MAX_BYTES = 20 * 1024 * 1024
PHOTO_EXT = (".jpg", ".jpeg", ".heic", ".heif")
BRANDS = (b"mp4", b"iso", b"qt  ", b"avc", b"hev", b"MSNV", b"M4V")
BOXES = {b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"uuid", b"meta", b"pnot", b"udta", b"sidx"}


def _boxes_end(data, start):
    """Fin du fichier MP4 qui commence à `start` (boîtes de premier niveau successives), ou None."""
    pos, seen = start, set()
    while pos + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind not in BOXES:
            break
        if size == 1:
            if pos + 16 > len(data):
                return None
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
        elif size == 0:
            size = len(data) - pos
        if size < 8 or pos + size > len(data):
            return None
        seen.add(kind)
        pos += size
    return pos if {b"moov", b"mdat"} <= seen else None


def embedded_video(path):
    """(début, fin) de la vidéo rangée dans une photo JPEG (Samsung, Google), ou None."""
    if not str(path).lower().endswith((".jpg", ".jpeg")):
        return None
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    pos = data.find(b"ftyp", 1024)
    while pos != -1:
        start = pos - 4
        size = struct.unpack(">I", data[start:pos])[0] if start >= 0 else 0
        if 12 <= size <= 64 and data[pos + 4:pos + 8].startswith(BRANDS):
            end = _boxes_end(data, start)
            if end:
                return start, end
        pos = data.find(b"ftyp", pos + 4)
    return None


def companion_video(path):
    """Vidéo .MOV d'une Live Photo d'iPhone (même nom, à côté de la photo), ou None."""
    path = Path(path)
    if path.suffix.lower() not in PHOTO_EXT:
        return None
    for ext in (".MOV", ".mov"):
        candidate = path.with_suffix(ext)
        try:
            if candidate.is_file() and candidate.stat().st_size <= LIVE_PHOTO_MAX_BYTES:
                return candidate
        except OSError:
            continue
    return None


def is_live_photo_video(path):
    """Ce .MOV est-il la partie vidéo d'une Live Photo ? (il n'est alors pas montré comme une vidéo à part)"""
    path = Path(path)
    if path.suffix.lower() != ".mov":
        return False
    try:
        if path.stat().st_size > LIVE_PHOTO_MAX_BYTES:
            return False
    except OSError:
        return False
    return any(path.with_suffix(ext).is_file() for ext in (".HEIC", ".heic", ".JPG", ".jpg", ".JPEG", ".jpeg"))


def has_motion(path):
    return embedded_video(path) is not None or companion_video(path) is not None


def animation_path(source, name):
    return CACHE_DIR / source / f"{Path(name).stem}.webp"


def prepared_box(prepared_jpg):
    """Rectangle (x, y, w, h) de la photo dans l'image préparée (noté par la préparation dans les EXIF)."""
    import piexif
    try:
        comment = piexif.load(str(prepared_jpg))["Exif"].get(piexif.ExifIFD.UserComment, b"")
        text = comment.decode("ascii", "ignore")
        if text.startswith("pimmich_bbox:"):
            x, y, w, h = (int(v) for v in text.split(":", 1)[1].split(","))
            return x, y, w, h
    except Exception:
        pass
    return None


def build_animation(photo_path, out_path, aspect, runner=None):
    """
    Crée l'animation WebP (quelques secondes, en boucle) au cadrage de la photo (`aspect` = largeur / hauteur).
    Retourne le chemin, ou None si la photo n'a pas de vidéo.
    """
    photo_path, out_path = Path(photo_path), Path(out_path)
    span = embedded_video(photo_path)
    clip = companion_video(photo_path)
    if not span and not clip:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_clip = None
    if span:
        temp_clip = out_path.with_suffix(".clip.mp4")
        with open(photo_path, "rb") as source, open(temp_clip, "wb") as target:
            source.seek(span[0])
            target.write(source.read(span[1] - span[0]))
        clip = temp_clip
    if aspect >= 1:
        width, height = MAX_SIDE, max(2, int(MAX_SIDE / aspect) // 2 * 2)
    else:
        width, height = max(2, int(MAX_SIDE * aspect) // 2 * 2), MAX_SIDE
    tmp = out_path.with_suffix(".tmp.webp")
    graph = f"fps={FPS},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    command = ["nice", "-n", "15", "ffmpeg", "-y", "-loglevel", "error", "-t", str(MAX_SECONDS), "-i", str(clip), "-an",
               "-vf", graph, "-c:v", "libwebp_anim", "-lossless", "0", "-q:v", "70", "-loop", "0", str(tmp)]
    try:
        result = (runner or subprocess.run)(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not tmp.exists():
            raise RuntimeError((result.stderr or "ffmpeg a échoué").strip()[-300:])
        os.replace(tmp, out_path)
        return out_path
    finally:
        tmp.unlink(missing_ok=True)
        if temp_clip:
            temp_clip.unlink(missing_ok=True)


def pending(width, height, sources=None):
    """Photos animées préparées dont l'animation n'est pas encore créée : [(source, nom)]."""
    from utils import animated
    from utils import prepare_all_photos as prep
    root = Path("static") / "photos"
    todo = []
    failed = _failed()
    for source in sources or (sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")) if root.is_dir() else []):
        prepared = Path("static") / "prepared" / source
        for entry in os.scandir(root / source) if (root / source).is_dir() else []:
            if not entry.is_file() or entry.name.startswith(".") or not entry.name.lower().endswith(PHOTO_EXT):
                continue
            shown = prepared / f"{Path(entry.name).stem}.jpg"
            if f"{source}/{entry.name}" in failed or animated.sidecar(shown).exists():
                continue
            if prep.preparation_state(prepared, entry.name, width, height) == "ok" and has_motion(entry.path):
                todo.append((source, entry.name))
    return todo


FAILED_FILE = CACHE_DIR / "failed.json"


def _failed():
    try:
        return json.loads(FAILED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _mark_failed(source, name, error):
    failed = _failed()
    failed[f"{source}/{name}"] = str(error)[:200]
    FAILED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FAILED_FILE.write_text(json.dumps(failed), encoding="utf-8")


def animate(source, name):
    """Crée l'animation d'une photo animée déjà préparée et la relie à sa photo préparée. Retourne True si c'est fait."""
    from utils import animated
    photo = Path("static") / "photos" / source / name
    shown = Path("static") / "prepared" / source / f"{photo.stem}.jpg"
    box = prepared_box(shown)
    if not box:
        return False
    x, y, w, h = box
    out = animation_path(source, name)
    try:
        if not (out.exists() and out.stat().st_mtime >= photo.stat().st_mtime):  # déjà créée (photo préparée à nouveau)
            out = build_animation(photo, out, w / h)
    except Exception as e:
        _mark_failed(source, name, e)
        return False
    if not out:
        return False
    animated.write(shown, [dict(animated.single_item(out, x, y, w, h), motion=True)])
    return True


def run(items, still_night=lambda: True):
    """Crée les animations demandées (une à la fois, avec les autres préparations). Retourne le nombre créé."""
    from utils import prepare_all_photos as prep
    made = 0
    for source, name in items:
        if not still_night():
            break
        with prep.PREPARE_LOCK:
            made += bool(animate(source, name))
    return made
