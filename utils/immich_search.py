"""
Recherche par contenu (« plage », « chien », « neige »...) grâce à Immich : son analyse des images (CLIP) tourne
sur le serveur Immich, pas sur le Raspberry Pi. Les résultats sont retrouvés parmi les photos importées d'Immich
(sources « immich » et « personnes »), d'après le nom du fichier d'origine.
"""
import time
from pathlib import Path

import requests

SOURCES = ("immich", "personnes")
CACHE_SECONDS = 600
_cache = {}


def available(config):
    return bool(config.get("immich_url") and config.get("immich_token"))


def smart_search(config, query, size=250, session=None):
    """Noms des fichiers trouvés par Immich, du plus pertinent au moins pertinent (sans extension, en minuscules)."""
    query = " ".join(str(query or "").split())[:120]
    if not query or not available(config):
        return []
    key = (config["immich_url"], query.lower())
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    response = (session or requests).post(f"{config['immich_url'].rstrip('/')}/api/search/smart",
                                          json={"query": query, "size": size, "page": 1},
                                          headers={"x-api-key": config["immich_token"], "Accept": "application/json"}, timeout=20)
    response.raise_for_status()
    items = ((response.json() or {}).get("assets") or {}).get("items") or []
    names = []
    for item in items:
        stem = Path(item.get("originalFileName") or "").stem.lower()
        if stem and stem not in names:
            names.append(stem)
    _cache[key] = (time.time(), names)
    return names


def rank(path, names):
    """Rang d'une photo de la bibliothèque dans les résultats d'Immich, ou None si elle n'y est pas."""
    source, _sep, rest = str(path).partition("/")
    if source not in SOURCES:
        return None
    stem = Path(rest).stem.lower()
    try:
        return names.index(stem)
    except ValueError:
        return None
