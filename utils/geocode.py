"""
Nom du lieu d'une photo (ville, pays) à partir de ses coordonnées GPS, via OpenStreetMap (Nominatim).

Désactivé par défaut (les coordonnées des photos sont envoyées à OpenStreetMap, jamais les photos) ; une fois
activé, chaque lieu (arrondi à ~1 km) n'est demandé qu'une fois et reste en cache sur le cadre. Respecte la
règle d'usage de Nominatim : une requête par seconde au plus, avec un identifiant d'application.
"""
import json
import threading
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "cache" / "places.json"
URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "Pimmich/1.0 (cadre photo familial ; https://github.com/Sweek-Adam/Pimmich-fork)"
_lock = threading.Lock()
_last_request = [0.0]


def _key(lat, lon):
    return f"{round(lat, 2):.2f},{round(lon, 2):.2f}"  # ~1 km : toutes les photos d'un même endroit partagent le résultat


def _load():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def cached(lat, lon):
    """Lieu déjà connu pour ces coordonnées, sinon None (aucune requête)."""
    if lat is None or lon is None:
        return None
    return _load().get(_key(lat, lon))


def lookup(lat, lon, language="fr"):
    """Lieu {city, country} : depuis le cache, sinon demandé à OpenStreetMap (puis mis en cache)."""
    if lat is None or lon is None:
        return None
    key = _key(lat, lon)
    with _lock:
        cache = _load()
        if key in cache:
            return cache[key]
        wait = 1.1 - (time.time() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.time()
        try:
            resp = requests.get(URL, timeout=10, headers={"User-Agent": USER_AGENT, "Accept-Language": language},
                                params={"format": "jsonv2", "lat": round(lat, 4), "lon": round(lon, 4), "zoom": 10})
            resp.raise_for_status()
            address = resp.json().get("address") or {}
        except (requests.RequestException, ValueError):
            return None  # nouvel essai plus tard
        place = {"city": address.get("city") or address.get("town") or address.get("village") or address.get("municipality")
                         or address.get("county") or "",
                 "country": address.get("country") or ""}
        cache[key] = place
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False))
        return place


def fill_places(index, language="fr", limit=60):
    """Demande les lieux encore inconnus des photos géolocalisées (par petits lots). Retourne le nombre demandé."""
    asked = 0
    cache = _load()
    for entry in index.values():
        lat, lon = entry.get("lat"), entry.get("lon")
        if lat is None or lon is None or _key(lat, lon) in cache:
            continue
        if asked >= limit:
            break
        place = lookup(lat, lon, language)
        asked += 1
        if place is not None:
            cache[_key(lat, lon)] = place
    return asked
