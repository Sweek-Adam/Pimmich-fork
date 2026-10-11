"""
Le soir et la nuit : la luminosité baisse doucement à partir d'une heure choisie (ou du coucher du soleil), et hors
des heures d'affichage le cadre peut montrer une horloge discrète au lieu de s'éteindre.
"""
from datetime import datetime

RAMP_MINUTES = 45  # la baisse se fait en douceur


def _minutes(value, default):
    try:
        hours, minutes = str(value).split(":")
        return int(hours) * 60 + int(minutes)
    except (TypeError, ValueError):
        return default


def morning(config, now):
    """Heure de début d'affichage du jour (minutes depuis minuit)."""
    key = "active_start_weekend" if now.weekday() >= 5 else "active_start_weekday"
    return _minutes(config.get(key, config.get("active_start", "07:00")), 7 * 60)


def dim_start(config, sunset=None):
    """Début de la baisse : l'heure choisie, ou le coucher du soleil (si connu)."""
    if config.get("dim_start", "21:00") == "sunset" and sunset is not None:
        return sunset.hour * 60 + sunset.minute
    return _minutes(config.get("dim_start", "21:00"), 21 * 60)


def brightness(config, now=None, sunset=None):
    """Luminosité des photos (1 = normale), de l'heure du soir jusqu'au matin."""
    if not config.get("dim_enabled"):
        return 1.0
    now = now or datetime.now()
    level = min(1.0, max(0.1, int(config.get("dim_level", 40)) / 100))
    start = dim_start(config, sunset)
    window = (morning(config, now) - start) % 1440 or 1440
    elapsed = (now.hour * 60 + now.minute - start) % 1440
    if elapsed >= window:
        return 1.0
    if elapsed < RAMP_MINUTES:
        return 1.0 - (1.0 - level) * elapsed / RAMP_MINUTES
    return level


def clock_at_night(config):
    """Hors des heures d'affichage : horloge de nuit (au lieu d'éteindre l'écran)."""
    return config.get("night_mode") == "clock"


def clock_color(config):
    """Couleur de l'horloge de nuit, assombrie selon la luminosité choisie (ambre : doux pour les yeux la nuit)."""
    level = min(1.0, max(0.05, int(config.get("night_brightness", 25)) / 100))
    base = {"amber": (255, 170, 70), "red": (255, 60, 40), "white": (235, 235, 235), "blue": (110, 160, 255)}.get(
        config.get("night_color", "amber"), (255, 170, 70))
    return tuple(int(c * level) for c in base)


def drift(now, width, height, box_w, box_h):
    """Position de l'horloge : elle se déplace un peu chaque minute (pas de marque sur l'écran)."""
    step = now.hour * 60 + now.minute
    free_w, free_h = max(0, width - box_w), max(0, height - box_h)
    x = free_w // 2 + int(free_w * 0.3 * ((step * 37 % 100) / 100 - 0.5))
    y = free_h // 2 + int(free_h * 0.3 * ((step * 53 % 100) / 100 - 0.5))
    return max(0, min(free_w, x)), max(0, min(free_h, y))
