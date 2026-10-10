"""
Index des photos du cadre : date de prise de vue et position GPS de chaque photo préparée.

Sources, par ordre de fiabilité : métadonnées Immich, EXIF de la photo (ou de son original), nom du fichier
(IMG-20260905-WA0016, PXL_20221129_192159116, 20251105_192938...). Sert à « Ce jour-là », à la carte,
aux légendes, à la recherche et aux albums intelligents. Mis à jour par petites touches : seules les photos
nouvelles ou modifiées sont lues.
"""
import json
import logging
import re
import threading
from datetime import date, datetime
from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
PREPARED_DIR = BASE_DIR / "static" / "prepared"
ORIGINALS_DIR = BASE_DIR / "static" / "photos"
INDEX_FILE = BASE_DIR / "cache" / "photo_index.json"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VARIANT = re.compile(r"_(polaroid|postcard|thumbnail)$")
SKIP_SOURCES = {"messages", "compositions"}  # pas des photos
logger = logging.getLogger(__name__)
_lock = threading.Lock()

# 2026-09-05, 20260905, 2026_09_05 (+ heure facultative 192938)
NAME_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?:[-_. T]?([01]\d|2[0-3])([0-5]\d)([0-5]\d))?(?!\d{3})")


def date_from_name(name):
    """Date lue dans le nom du fichier (téléphones, WhatsApp), sinon None."""
    for match in NAME_DATE.finditer(Path(name).stem):
        year, month, day, hh, mm, ss = match.groups()
        try:
            value = datetime(int(year), int(month), int(day), int(hh or 12), int(mm or 0), int(ss or 0))
        except ValueError:
            continue
        if 1990 <= value.year <= date.today().year + 1:
            return value
    return None


def _ratio(value):
    try:
        return float(value[0]) / float(value[1]) if isinstance(value, tuple) else float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _gps(gps):
    """Latitude / longitude décimales depuis le bloc GPS de l'EXIF."""
    try:
        lat = sum(_ratio(v) / 60 ** i for i, v in enumerate(gps[2]))
        lon = sum(_ratio(v) / 60 ** i for i, v in enumerate(gps[4]))
    except (KeyError, TypeError, IndexError):
        return None, None
    if gps.get(1) in ("S", b"S"):
        lat = -lat
    if gps.get(3) in ("W", b"W"):
        lon = -lon
    if abs(lat) < 1e-6 and abs(lon) < 1e-6:
        return None, None
    return round(lat, 6), round(lon, 6)


def read_exif(path):
    """(date, latitude, longitude) d'après l'EXIF (sans décoder l'image), sinon (None, None, None)."""
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal, sinon DateTime
            lat, lon = _gps(exif.get_ifd(0x8825)) if exif.get_ifd(0x8825) else (None, None)
    except Exception:
        return None, None, None
    taken = None
    if raw:
        try:
            taken = datetime.strptime(str(raw).strip("\x00")[:19], "%Y:%m:%d %H:%M:%S")
        except ValueError:
            taken = None
    return taken, lat, lon


def _original(prepared):
    """Fichier original correspondant (même nom, extension quelconque) dans static/photos/<source>."""
    folder = ORIGINALS_DIR / prepared.parent.name
    if not folder.is_dir():
        return None
    for candidate in folder.glob(prepared.stem + ".*"):
        return candidate
    return None


def _immich(prepared):
    try:
        from utils.metadata_utils import get_photo_metadata
        meta = get_photo_metadata(str(prepared)) or {}
    except Exception:
        return {}
    for field in ("dateTimeOriginal", "DateTimeOriginal", "subSecDateTimeOriginal", "createDate", "CreateDate", "date_taken"):
        if meta.get(field):
            try:
                meta = dict(meta, _date=datetime.fromisoformat(str(meta[field]).replace("Z", "+00:00")).replace(tzinfo=None))
                break
            except ValueError:
                continue
    return meta


def photo_info(prepared):
    """Informations d'une photo préparée : {date (ISO), how (immich|exif|name), lat, lon}."""
    prepared = Path(prepared)
    meta = _immich(prepared)
    taken, how = meta.get("_date"), "immich" if meta.get("_date") else None
    lat, lon = meta.get("latitude"), meta.get("longitude")
    if not taken or lat is None:
        exif_date, exif_lat, exif_lon = read_exif(prepared)
        if exif_date is None or exif_lat is None:
            original = _original(prepared)
            if original:
                o_date, o_lat, o_lon = read_exif(original)
                exif_date, exif_lat, exif_lon = exif_date or o_date, exif_lat if exif_lat is not None else o_lat, exif_lon if exif_lon is not None else o_lon
        if not taken and exif_date:
            taken, how = exif_date, "exif"
        if lat is None and exif_lat is not None:
            lat, lon = exif_lat, exif_lon
    if not taken:
        taken = date_from_name(prepared.name)
        how = "name" if taken else None
    return {"date": taken.isoformat(timespec="seconds") if taken else None, "how": how,
            "lat": lat if isinstance(lat, (int, float)) else None, "lon": lon if isinstance(lon, (int, float)) else None}


def load():
    try:
        return json.loads(INDEX_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _photos(prepared_dir):
    for source in sorted(prepared_dir.iterdir()) if prepared_dir.is_dir() else []:
        if not source.is_dir() or source.name in SKIP_SOURCES or source.name.startswith("."):
            continue
        for path in source.iterdir():
            if path.suffix.lower() in IMAGE_EXT and not VARIANT.search(path.stem):
                yield path


def update(prepared_dir=None, limit=None):
    """Ajoute les photos nouvelles ou modifiées, retire les disparues. Retourne le nombre de photos lues."""
    prepared_dir = Path(prepared_dir or PREPARED_DIR)
    with _lock:
        index, seen, read = load(), set(), 0
        for path in _photos(prepared_dir):
            key = f"{path.parent.name}/{path.name}"
            seen.add(key)
            mtime = int(path.stat().st_mtime)
            if index.get(key, {}).get("mtime") == mtime:
                continue
            if limit is not None and read >= limit:
                continue  # le reste à la prochaine fois (le diaporama ne doit pas attendre)
            index[key] = dict(photo_info(path), mtime=mtime)
            read += 1
        removed = [k for k in index if k not in seen]
        for key in removed:
            index.pop(key)
        if read or removed:
            INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = INDEX_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(index, ensure_ascii=False))
            tmp.replace(INDEX_FILE)
        return read


def key_for(path):
    """Clé d'index d'un chemin préparé (variantes polaroïd / carte postale ramenées à la photo)."""
    path = Path(path)
    return f"{path.parent.name}/{VARIANT.sub('', path.stem)}{path.suffix}"


def info(path, index=None):
    return (index if index is not None else load()).get(key_for(path)) or {}


def taken(path, index=None):
    value = info(path, index).get("date")
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def on_this_day(today=None, index=None):
    """Photos prises un jour comme aujourd'hui, les années précédentes : [(clé, date)], les plus anciennes d'abord."""
    today = today or date.today()
    found = []
    for key, entry in (index if index is not None else load()).items():
        try:
            when = datetime.fromisoformat(entry["date"]) if entry.get("date") else None
        except ValueError:
            continue
        if when and when.month == today.month and when.day == today.day and when.year < today.year:
            found.append((key, when))
    return sorted(found, key=lambda item: item[1])
