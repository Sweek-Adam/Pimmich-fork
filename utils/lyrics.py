"""
Paroles synchronisées pour le karaoké, depuis LRCLIB (annuaire libre et gratuit, https://lrclib.net) : seuls le titre,
l'artiste, l'album et la durée du morceau sont envoyés. Les paroles sont gardées en cache sur le cadre.
"""
import hashlib
import json
import re
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "cache" / "lyrics"
API = "https://lrclib.net/api"
HEADERS = {"User-Agent": "Pimmich/1.0 (cadre photo ; https://github.com/Sweek-Adam/Pimmich-fork)"}
LINE = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")


def parse_lrc(text):
    """Paroles LRC (« [01:23.45] ligne ») -> [(secondes, ligne)], triées."""
    lines = []
    for raw in (text or "").splitlines():
        stamps = list(LINE.finditer(raw))
        if not stamps:
            continue
        words = LINE.sub("", raw).strip()
        for m in stamps:
            fraction = m.group(3) or "0"
            seconds = int(m.group(1)) * 60 + int(m.group(2)) + int(fraction) / (10 ** len(fraction))
            lines.append((round(seconds, 2), words))
    return sorted(lines)


def line_index(lines, t):
    """Indice de la ligne chantée au temps t (-1 avant la première)."""
    index = -1
    for i, (start, _words) in enumerate(lines):
        if start <= t:
            index = i
        else:
            break
    return index


def _cache_path(title, artist):
    return CACHE_DIR / (hashlib.sha1(f"{artist}|{title}".lower().encode()).hexdigest()[:20] + ".json")


def fetch(title, artist, album="", duration=None, session=None):
    """Paroles synchronisées [(secondes, ligne)] d'un morceau, ou [] si introuvables (le résultat est mis en cache)."""
    if not title:
        return []
    path = _cache_path(title, artist)
    try:
        return [tuple(x) for x in json.loads(path.read_text(encoding="utf-8"))]
    except (OSError, ValueError):
        pass
    session = session or requests
    synced = None
    try:
        params = {"track_name": title, "artist_name": artist or ""}
        if album:
            params["album_name"] = album
        if duration:
            params["duration"] = int(duration)
        response = session.get(f"{API}/get", params=params, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            synced = (response.json() or {}).get("syncedLyrics")
        if not synced:
            response = session.get(f"{API}/search", params={"track_name": title, "artist_name": artist or ""}, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                synced = next((r.get("syncedLyrics") for r in response.json() or [] if r.get("syncedLyrics")), None)
    except (requests.RequestException, ValueError):
        return []  # pas de cache : on réessaiera
    lines = parse_lrc(synced)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    return lines
