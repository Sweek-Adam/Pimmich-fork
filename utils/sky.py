"""
Soleil et lune, calculés sur le cadre (aucun service en ligne) : heures de lever et de coucher du soleil
(algorithme de la NOAA, précision de l'ordre de la minute) et phase de la lune.
"""
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

LOCATION_FILE = Path(__file__).resolve().parent.parent / "cache" / "location.json"

SYNODIC_MONTH = 29.530588853
NEW_MOON_REFERENCE = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)  # nouvelle lune de référence
PHASES = ("new", "waxing_crescent", "first_quarter", "waxing_gibbous", "full", "waning_gibbous", "last_quarter", "waning_crescent")


def _sun_utc_minutes(day, lat, lon, rising):
    """Minutes UTC depuis minuit du lever (ou coucher) du soleil ; None s'il ne se lève / couche pas (pôles)."""
    n = day.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1 + 0.5)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) - 0.006758 * math.cos(2 * gamma)
            + 0.000907 * math.sin(2 * gamma) - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma))
    zenith = math.radians(90.833)
    phi = math.radians(lat)
    cos_ha = math.cos(zenith) / (math.cos(phi) * math.cos(decl)) - math.tan(phi) * math.tan(decl)
    if not -1 <= cos_ha <= 1:
        return None
    ha = math.degrees(math.acos(cos_ha))
    return 720 - 4 * (lon + (ha if rising else -ha)) - eqtime


def sun_times(lat, lon, day=None, tz=None):
    """(lever, coucher) en heure locale (datetime sans fuseau), ou (None, None) près des pôles."""
    day = day or date.today()
    result = []
    for rising in (True, False):
        minutes = _sun_utc_minutes(day, lat, lon, rising)
        if minutes is None:
            result.append(None)
            continue
        utc = datetime.combine(day, time(0, 0), tzinfo=timezone.utc) + timedelta(minutes=minutes)
        result.append(utc.astimezone(tz).replace(tzinfo=None))
    return tuple(result)


def moon(at=None):
    """Phase de la lune : {age (jours), illumination (0..1), phase (new, full...), waxing}."""
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        at = at.astimezone(timezone.utc)
    age = ((at - NEW_MOON_REFERENCE).total_seconds() / 86400) % SYNODIC_MONTH
    illumination = (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH)) / 2
    index = int((age / SYNODIC_MONTH) * 8 + 0.5) % 8
    return {"age": round(age, 1), "illumination": round(illumination, 3), "phase": PHASES[index], "waxing": age < SYNODIC_MONTH / 2}


def location(config=None):
    """Coordonnées du cadre (lat, lon) : réglage manuel, sinon celles de la ville de la météo (mémorisées), sinon None."""
    config = config or {}
    try:
        return float(config["latitude"]), float(config["longitude"])
    except (KeyError, TypeError, ValueError):
        pass
    try:
        data = json.loads(LOCATION_FILE.read_text())
        return float(data["lat"]), float(data["lon"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remember_location(lat, lon):
    """Mémorise les coordonnées de la ville de la météo (une écriture seulement si elles changent)."""
    try:
        lat, lon = round(float(lat), 3), round(float(lon), 3)
    except (TypeError, ValueError):
        return
    if location() == (lat, lon):
        return
    LOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCATION_FILE.write_text(json.dumps({"lat": lat, "lon": lon}))


def today(config=None, now=None):
    """Soleil et lune du jour pour le cadre : {sunrise, sunset, moon} (soleil absent sans coordonnées)."""
    now = now or datetime.now()
    found = {"moon": moon(now.astimezone(timezone.utc))}
    coords = location(config)
    if coords:
        found["sunrise"], found["sunset"] = sun_times(coords[0], coords[1], now.date())
    return found


def moon_image(size, age, lit=(245, 240, 220), dark=(70, 70, 80)):
    """Icône de la lune (image RGBA de Pillow) : partie éclairée selon son âge (0 : nouvelle lune, 14,8 : pleine)."""
    from PIL import Image
    theta = 2 * math.pi * (age % SYNODIC_MONTH) / SYNODIC_MONTH
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = image.load()
    r = size / 2 - 0.5
    for py in range(size):
        dy = py - r
        if abs(dy) > r:
            continue
        w = math.sqrt(r * r - dy * dy)
        t = w * math.cos(theta)
        low, high = (t, w) if theta < math.pi else (-w, -t)  # croissante : à droite ; décroissante : à gauche
        for px in range(size):
            dx = px - r
            if abs(dx) <= w:
                pixels[px, py] = (*(lit if low <= dx <= high else dark), 255)
    return image
