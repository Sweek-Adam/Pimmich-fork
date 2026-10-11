"""
Recadrage intelligent : quand une photo doit être coupée (cases des compositions, photos très larges), la fenêtre
gardée contient les visages entiers au lieu du centre de l'image.

Visages détectés par YuNet (OpenCV, petit modèle rapide même sur Raspberry Pi 3) et mémorisés par photo dans
cache/faces.json (coordonnées relatives : elles restent justes après redimensionnement). Sans OpenCV, le
recadrage reste celui d'avant (centre légèrement remonté).
"""
import json
import logging
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL = BASE_DIR / "resources" / "face_detection_yunet_2023mar.onnx"
CACHE_FILE = BASE_DIR / "cache" / "faces.json"
DETECT_SIDE = 640      # la détection se fait sur une copie réduite
MIN_SCORE = 0.75
MARGIN = 0.35          # marge autour d'un visage (cheveux, menton) en proportion de sa taille
INFO_KEY = "pimmich_faces"
logger = logging.getLogger("pimmich.faces")
_lock = threading.Lock()
_detector = None
_cache = None
ENABLED = True


def set_enabled(enabled):
    global ENABLED
    ENABLED = bool(enabled)


def available():
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    return MODEL.is_file()


def _get_detector():
    global _detector
    if _detector is None:
        import cv2
        _detector = cv2.FaceDetectorYN.create(str(MODEL), "", (320, 320), MIN_SCORE, 0.3, 50)
    return _detector


def detect(image):
    """Visages d'une image PIL : [(x, y, w, h)] en proportions de l'image (0..1), les plus grands d'abord."""
    if not ENABLED or not available():
        return []
    import numpy
    small = image.convert("RGB")
    if max(small.size) > DETECT_SIDE:
        small = small.copy()
        small.thumbnail((DETECT_SIDE, DETECT_SIDE))
    w, h = small.size
    pixels = numpy.asarray(small)[:, :, ::-1].copy()  # RGB -> BGR
    with _lock:
        detector = _get_detector()
        detector.setInputSize((w, h))
        _ok, found = detector.detect(pixels)
    faces = []
    for row in found if found is not None else []:
        x, y, fw, fh, score = float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[-1])
        if score >= MIN_SCORE and fw > 0 and fh > 0:
            x0, y0 = max(0.0, x / w), max(0.0, y / h)
            faces.append((round(x0, 4), round(y0, 4), round(min(1 - x0, fw / w), 4), round(min(1 - y0, fh / h), 4)))
    return sorted(faces, key=lambda f: -f[2] * f[3])


def _load_cache():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text())
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _save_cache():
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_cache, separators=(",", ":")))
        tmp.replace(CACHE_FILE)
    except OSError as e:
        logger.debug(f"Cache des visages non enregistré : {e}")


def for_file(path, image):
    """Visages d'une photo (image déjà ouverte et orientée), mémorisés selon le fichier et sa date."""
    if not ENABLED or not available():
        return []
    path = Path(path)
    try:
        key, stamp = str(path.resolve().relative_to(BASE_DIR)), int(path.stat().st_mtime)
    except (OSError, ValueError):
        key, stamp = str(path), 0
    cache = _load_cache()
    known = cache.get(key)
    if known and known.get("t") == stamp:
        return [tuple(f) for f in known.get("f", [])]
    try:
        faces = detect(image)
    except Exception as e:
        logger.debug(f"Détection des visages impossible ({path.name}) : {e}")
        faces = []
    cache[key] = {"t": stamp, "f": faces}
    _save_cache()
    return faces


def attach(image, faces):
    """Joint les visages à l'image (ils suivent les copies et redimensionnements de Pillow)."""
    image.info[INFO_KEY] = list(faces)
    return image


def window(img_w, img_h, crop_w, crop_h, faces, focus_y=0.42):
    """Position (left, top) d'une fenêtre crop_w × crop_h dans l'image, qui garde les visages entiers si possible."""
    max_left, max_top = max(0, img_w - crop_w), max(0, img_h - crop_h)
    left, top = max_left // 2, int(max_top * focus_y)
    if not faces:
        return left, top
    boxes = []
    for x, y, w, h in faces:
        mx, my = w * MARGIN, h * MARGIN
        boxes.append(((x - mx) * img_w, (y - my) * img_h, (x + w + mx) * img_w, (y + h + my * 1.5) * img_h))
    # Le plus de visages possible : on part de tous, puis on retire les plus petits tant qu'ils ne tiennent pas
    for count in range(len(boxes), 0, -1):
        group = boxes[:count]
        x0, y0 = min(b[0] for b in group), min(b[1] for b in group)
        x1, y1 = max(b[2] for b in group), max(b[3] for b in group)
        if (x1 - x0 <= crop_w and y1 - y0 <= crop_h) or count == 1:
            break
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left = cx - crop_w / 2
    if y1 - y0 <= crop_h:
        # Visages un peu au-dessus du centre (règle des tiers), sans couper ni le haut ni le bas du groupe
        top = min(max(cy - crop_h * 0.45, y1 - crop_h), y0)
    else:
        top = cy - crop_h / 2  # visage plus grand que la fenêtre : on le centre
    return int(min(max_left, max(0, left))), int(min(max_top, max(0, top)))
