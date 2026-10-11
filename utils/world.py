"""
Fond de carte hors ligne : contours des pays (Natural Earth 1:50m, resources/world_countries.json).
Sert à savoir dans quel pays une photo a été prise (sans aucune requête sur internet) et à dessiner les cartes.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

WORLD_FILE = Path(__file__).resolve().parent.parent / "resources" / "world_countries.json"


@lru_cache(maxsize=1)
def countries():
    """[{iso, names, polygons: [[ring, ...], ...], bbox: (min_lon, min_lat, max_lon, max_lat)}]."""
    data = json.loads(WORLD_FILE.read_text(encoding="utf-8"))
    found = []
    for feature in data["features"]:
        polygons = feature["geometry"]["coordinates"]
        xs = [p[0] for poly in polygons for p in poly[0]]
        ys = [p[1] for poly in polygons for p in poly[0]]
        found.append({"iso": feature["properties"].get("iso"), "names": feature["properties"].get("names") or {},
                      "polygons": polygons, "bbox": (min(xs), min(ys), max(xs), max(ys))})
    return found


def _inside(ring, lon, lat):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def country_at(lat, lon):
    """Pays où se trouve ce point (dict de countries()), sinon None (en mer, ou trop près d'une côte découpée)."""
    if lat is None or lon is None:
        return None
    for country in countries():
        x0, y0, x1, y1 = country["bbox"]
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for polygon in country["polygons"]:
            if _inside(polygon[0], lon, lat) and not any(_inside(hole, lon, lat) for hole in polygon[1:]):
                return country
    return None


def country_name(country, language="fr"):
    if not country:
        return ""
    names = country.get("names") or {}
    return names.get((language or "fr")[:2]) or names.get("en") or ""


def distance_km(a, b):
    """Distance à vol d'oiseau entre deux points (lat, lon)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(h)))
