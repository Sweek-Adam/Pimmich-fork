"""
Détection des photos en double entre sources (ex. même photo reçue par Google Drive et par Telegram).

Chaque image reçoit une empreinte visuelle (dHash 64 bits) qui varie très peu quand la photo est recompressée
ou redimensionnée. Deux photos dont les empreintes diffèrent d'au plus MAX_DISTANCE bits sont considérées
identiques. Les empreintes sont mises en cache (chemin, date de modification, taille).
"""
import json
import logging
import threading
from pathlib import Path

from PIL import Image

logger = logging.getLogger("pimmich.dedup")

PROJECT_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = PROJECT_DIR / "cache" / "image_hashes.json"
MAX_DISTANCE = 3   # bits différents tolérés sur 64
BANDS = 4          # découpage de l'empreinte : deux images proches partagent forcément une bande identique
_lock = threading.Lock()


def dhash(path):
    with Image.open(path) as image:
        image.draft("L", (image.width // 8 or 1, image.height // 8 or 1))  # décodage JPEG accéléré
        small = image.convert("L").resize((9, 8), Image.LANCZOS)
    pixels = list(small.getdata())
    value = 0
    for row in range(8):
        for col in range(8):
            value = (value << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return value


def _load_cache():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache))
    tmp.replace(CACHE_FILE)


def hashes_for(paths):
    """Empreinte de chaque image (None si illisible), en réutilisant le cache quand le fichier n'a pas changé."""
    with _lock:
        cache = _load_cache()
        result, changed = {}, False
        for path in paths:
            key = str(path)
            try:
                stat = Path(path).stat()
            except OSError:
                result[key] = None
                continue
            cached = cache.get(key)
            if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
                result[key] = cached[2]
                continue
            try:
                value = dhash(path)
            except Exception as e:
                logger.debug(f"Empreinte impossible pour {path} : {e}")
                value = None
            cache[key] = [stat.st_mtime, stat.st_size, value]
            result[key] = value
            changed = True
        # Oublier les fichiers disparus pour que le cache ne grossisse pas indéfiniment
        existing = {k: v for k, v in cache.items() if Path(k).exists()}
        if changed or len(existing) != len(cache):
            _save_cache(existing)
    return result


def _bands(value):
    return [(i, (value >> (16 * i)) & 0xFFFF) for i in range(BANDS)]


def remove_duplicates(paths):
    """
    Retourne `paths` sans les doublons visuels, en gardant la première occurrence (l'ordre des sources compte).
    Les fichiers non hachables (vidéos, images illisibles) sont toujours conservés.
    """
    images = [p for p in paths if Path(p).suffix.lower() in (".jpg", ".jpeg", ".png")]
    hashes = hashes_for(images)
    buckets = {}
    kept, duplicates = [], 0
    for path in paths:
        value = hashes.get(str(path))
        if value is None:
            kept.append(path)
            continue
        candidates = {c for band in _bands(value) for c in buckets.get(band, ())}
        if any(bin(value ^ c).count("1") <= MAX_DISTANCE for c in candidates):
            duplicates += 1
            continue
        for band in _bands(value):
            buckets.setdefault(band, []).append(value)
        kept.append(path)
    if duplicates:
        logger.info(f"[Doublons] {duplicates} photo(s) en double masquée(s) dans le diaporama")
    return kept
