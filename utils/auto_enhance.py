"""
Amélioration automatique des photos trop sombres ou ternes, à la préparation (l'original n'est jamais modifié).

Mesures sur une petite copie : luminosité moyenne, étendue des tons (centiles 1 % et 99 %), saturation moyenne.
- Photo terne (tons resserrés) : les tons sont étirés, à moitié seulement, avec les mêmes bornes pour les trois
  couleurs (pas de dominante ajoutée) ;
- photo sombre : les ombres sont éclaircies (courbe gamma), sans brûler les hautes lumières ;
- couleurs fades : un peu plus de saturation.
Les photos de nuit voulues (sombres mais avec des lumières vives : feux d'artifice, bougies, ville) et les éclairages
colorés voulus (soirée, concert) sont laissés tels quels, comme les photos déjà correctes.
"""
import math

from PIL import Image, ImageEnhance, ImageStat

DARK = 85             # luminosité moyenne en dessous de laquelle la photo est jugée sombre
NARROW = 170          # étendue des tons (1 % -> 99 %) en dessous de laquelle elle est jugée terne
DULL = 60             # saturation moyenne (0-255) en dessous de laquelle les couleurs sont fades
STRETCH_SHARE = 0.55  # part de l'étirement complet appliquée (correction douce)
MIN_GAMMA = 0.78      # éclaircissement le plus fort (plus bas, les ombres des JPEG se cassent en marches)


def _percentile(histogram, share):
    total, running = sum(histogram), 0
    for value, count in enumerate(histogram):
        running += count
        if running >= total * share:
            return value
    return 255


def measure(img):
    small = img.convert("RGB").copy()
    small.thumbnail((256, 256))
    gray = small.convert("L")
    histogram = gray.histogram()
    saturation = ImageStat.Stat(small.convert("HSV").getchannel("S")).mean[0]
    channels = ImageStat.Stat(small).mean
    return {"mean": ImageStat.Stat(gray).mean[0], "low": _percentile(histogram, 0.01), "high": _percentile(histogram, 0.99),
            "saturation": saturation, "cast": max(channels) / max(1.0, min(channels))}


def plan(m):
    """Corrections à faire d'après les mesures : {stretch: (bas, haut), gamma, color} (vide : rien à faire)."""
    if m["mean"] < 60 and m["high"] > 235:
        return {}  # nuit voulue : sombre, mais avec des lumières vives
    if m["high"] - m["low"] < 25:
        return {}  # image presque unie (dessin, fond, carte) : pas une photo à corriger
    if m.get("cast", 1) > 1.8:
        return {}  # éclairage coloré voulu (soirée, concert, néons) : on garde l'ambiance
    out = {}
    if m["high"] - m["low"] < NARROW:
        low = m["low"] * STRETCH_SHARE
        high = 255 - (255 - m["high"]) * STRETCH_SHARE
        out["stretch"] = (low, high)
    mean = m["mean"]
    if "stretch" in out:
        low, high = out["stretch"]
        mean = (mean - low) * 255 / max(1, high - low)
    if mean < DARK:
        out["gamma"] = max(MIN_GAMMA, min(1.0, math.log(0.42) / math.log(max(mean, 8) / 255)))
    if m["saturation"] < DULL and out:
        out["color"] = 1.12
    return out


def enhance(img, steps):
    if not steps:
        return img
    low, high = steps.get("stretch", (0, 255))
    gamma = steps.get("gamma", 1.0)
    table = []
    for value in range(256):
        x = min(1.0, max(0.0, (value - low) / max(1, high - low)))
        table.append(int(round(255 * (x ** gamma))))
    img = img.convert("RGB").point(table * 3)
    if steps.get("color"):
        img = ImageEnhance.Color(img).enhance(steps["color"])
    return img


def auto(img):
    """Photo améliorée si elle est sombre ou terne, sinon la même ; (image, corrections appliquées)."""
    steps = plan(measure(img))
    return enhance(img, steps), steps
