"""
Tri automatique des photos : écarte du diaporama les photos floues, très sombres, les captures d'écran et les
rafales (même scène prise plusieurs fois en quelques secondes : seule la plus nette est gardée).

Les mesures sont faites une fois (index des photos) sur le centre de l'image préparée (sans les bandes floues
ajoutées sur les côtés). Seuils prudents ; chaque photo écartée peut être remise d'un clic.
"""
import re
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

DARK = 28            # luminosité moyenne (0-255) en dessous de laquelle une photo est « très sombre »
BLURRY = 4.0         # netteté (variance du laplacien) en dessous de laquelle une photo est nettement floue (prudent)
BURST_SECONDS = 15   # photos prises à moins de 15 s d'écart...
BURST_DISTANCE = 12  # ... et visuellement proches (bits d'empreinte différents sur 64) : une rafale
SCREENSHOT_NAME = re.compile(r"screenshot|screen[ _-]?shot|capture[ _-]?d.?[ée]cran|bildschirmfoto|captura|スクリーンショット|scrnshot", re.I)
REASONS = ("blurry", "dark", "screenshot", "burst")


def measure(path):
    """Mesures d'une photo préparée : {b: luminosité, s: netteté}."""
    try:
        with Image.open(path) as image:
            image.draft("L", (640, 640))
            gray = image.convert("L")
            gray.thumbnail((640, 640))
            w, h = gray.size
            center = gray.crop((int(w * 0.2), int(h * 0.15), int(w * 0.8), int(h * 0.85)))  # sans les bandes floues
            brightness = ImageStat.Stat(center).mean[0]
            # Netteté : variance du laplacien (bords de l'image exclus : le filtre y voit de faux contours)
            laplacian = center.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
            lw, lh = laplacian.size
            sharpness = ImageStat.Stat(laplacian.crop((3, 3, lw - 3, lh - 3))).var[0]
    except Exception:
        return {}
    return {"b": round(brightness, 1), "s": round(sharpness, 1)}


def is_screenshot(path, original=None, has_camera=False):
    """Capture d'écran : nom de fichier explicite, ou PNG sans appareil photo dans les informations de l'image."""
    name = Path(original or path).name
    if SCREENSHOT_NAME.search(name):
        return True
    return Path(original or path).suffix.lower() == ".png" and not has_camera


def reasons(entry, config=None):
    """Raisons d'écarter une photo de l'index (selon les critères activés)."""
    config = config or {}
    found = []
    q = entry.get("q") or {}
    if config.get("filter_blurry", True) and q.get("s") is not None and q["s"] < BLURRY:
        found.append("blurry")
    if config.get("filter_dark", True) and q.get("b") is not None and q["b"] < DARK:
        found.append("dark")
    if config.get("filter_screenshots", True) and q.get("shot"):
        found.append("screenshot")
    return found


def bursts(index, hashes):
    """
    Rafales : photos prises à moins de BURST_SECONDS d'écart et visuellement proches. Retourne l'ensemble des
    clés à écarter (toutes sauf la plus nette de chaque rafale). `hashes` : {clé: empreinte dHash}.
    """
    from datetime import datetime
    dated = []
    for key, entry in index.items():
        try:
            when = datetime.fromisoformat(entry["date"]) if entry.get("date") else None
        except ValueError:
            when = None
        if when and entry.get("how") in ("exif", "immich") and key in hashes:  # heure fiable seulement
            dated.append((when, key))
    dated.sort()
    excluded, group = set(), []  # group : [(date, clé)] de la rafale en cours

    def close_group():
        if len(group) > 1:
            best = max(group, key=lambda item: (index[item[1]].get("q") or {}).get("s", 0))
            excluded.update(key for _when, key in group if key != best[1])

    for when, key in dated:
        if group:
            last_when, last_key = group[-1]
            near = (when - last_when).total_seconds() <= BURST_SECONDS and bin(hashes[key] ^ hashes[last_key]).count("1") <= BURST_DISTANCE
            if not near:
                close_group()
                group = []
        group.append((when, key))
    close_group()
    return excluded


def excluded(index, config, hashes=None):
    """Photos écartées : {clé: [raisons]} (hors photos remises à la main)."""
    if not config.get("auto_filter_enabled", True):
        return {}
    keep = set(config.get("quality_keep") or [])
    out = {}
    for key, entry in index.items():
        found = reasons(entry, config)
        if found and key not in keep:
            out[key] = found
    if hashes and config.get("filter_bursts", True):
        for key in bursts(index, hashes):
            if key not in keep:
                out.setdefault(key, []).append("burst")
    return out
