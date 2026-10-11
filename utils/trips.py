"""
Voyages et sorties : les photos sont regroupées par moments (prises à peu d'heures d'intervalle), puis situées.

- un groupe pris loin de la maison est un « voyage », près de la maison une « sortie » ;
- un groupe sans position GPS est un « moment à placer » : on peut le situer à la main (clic sur la carte ou recherche),
  la position est alors gardée pour chacune de ses photos (cache/trip_places.json) ;
- la maison : la position du cadre (réglage ou ville de la météo), sinon l'endroit le plus photographié ;
- les noms de pays viennent du fond de carte hors ligne ; les villes, du cache du géocodage s'il est activé, ou du nom
  donné à la main.
"""
import hashlib
import json
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from utils import world

BASE_DIR = Path(__file__).resolve().parent.parent
PLACES_FILE = BASE_DIR / "cache" / "trip_places.json"
GAP_HOURS = 36          # au-delà, c'est un autre moment
HOME_SWITCH_HOURS = 3   # départ de la maison ou retour : nouveau moment dès 3 h d'écart
TRIP_KM = 50            # au-delà de 50 km de la maison : voyage
MIN_PHOTOS = 3
MAX_DAYS_AT_HOME = 21   # un « moment » plus long, à la maison ou sans position, c'est la vie de tous les jours
_lock = threading.Lock()


# --- Positions données à la main ---

def manual_places():
    try:
        return json.loads(PLACES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_place(keys, lat, lon, name=""):
    """Situe ces photos (celles qui n'ont pas déjà une position GPS sont concernées à l'affichage)."""
    lat, lon = round(float(lat), 5), round(float(lon), 5)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordonnées invalides.")
    with _lock:
        places = manual_places()
        for key in keys:
            places[key] = {"lat": lat, "lon": lon, "name": str(name or "").strip()[:80]}
        _save(places)


def clear_place(keys):
    with _lock:
        places = manual_places()
        for key in keys:
            places.pop(key, None)
        _save(places)


def _save(places):
    PLACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PLACES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(places, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PLACES_FILE)


# --- Regroupement ---

def _points(index, manual):
    points = []
    for key, entry in index.items():
        try:
            when = datetime.fromisoformat(entry["date"]) if entry.get("date") else None
        except ValueError:
            when = None
        if when is None:
            continue
        lat, lon, name, how = entry.get("lat"), entry.get("lon"), "", "gps"
        if lat is None or lon is None:
            placed = manual.get(key)
            lat, lon, name, how = (placed["lat"], placed["lon"], placed.get("name", ""), "manual") if placed else (None, None, "", None)
        else:
            name = (manual.get(key) or {}).get("name", "")  # un nom donné à la main reste prioritaire
        points.append({"key": key, "when": when, "lat": lat, "lon": lon, "name": name, "how": how, "q": entry.get("q")})
    points.sort(key=lambda p: (p["when"], p["key"]))
    return points


def find_home(points, config=None):
    """Position de la maison : celle du cadre, sinon l'endroit (≈ 25 km) le plus photographié, sinon None."""
    from utils import sky
    located = sky.location(config or {})
    if located:
        return located
    cells = Counter((round(p["lat"] * 4) / 4, round(p["lon"] * 4) / 4) for p in points if p["lat"] is not None)
    return cells.most_common(1)[0][0] if cells else None


def _at_home(point, home):
    return home is not None and point["lat"] is not None and world.distance_km(home, (point["lat"], point["lon"])) <= TRIP_KM


def _split(points, home):
    groups, current, last_located = [], [], None
    for point in points:
        if current:
            gap = (point["when"] - current[-1]["when"]).total_seconds() / 3600
            moved = (point["lat"] is not None and last_located is not None
                     and _at_home(point, home) != _at_home(last_located, home) and gap > HOME_SWITCH_HOURS)
            if gap > GAP_HOURS or moved:
                groups.append(current)
                current = []
        current.append(point)
        if point["lat"] is not None:
            last_located = point
    if current:
        groups.append(current)
    return groups


def _score(quality):
    """Photo de couverture : nette et lumineuse, jamais une capture d'écran (mesures de utils/photo_quality)."""
    if not isinstance(quality, dict) or quality.get("shot"):
        return 0
    brightness, sharpness = quality.get("b") or 0, quality.get("s") or 0
    return 0 if brightness < 40 or brightness > 235 else min(sharpness, 60)


def _place_names(group, language, cached_place):
    names = Counter(p["name"] for p in group if p["name"])
    countries, seen = [], set()
    for p in group:
        if p["lat"] is None:
            continue
        country = world.country_at(p["lat"], p["lon"])
        if country and country["iso"] not in seen:
            seen.add(country["iso"])
            countries.append({"iso": country["iso"], "name": world.country_name(country, language)})
    cities = Counter()
    for p in group:
        place = cached_place(p["lat"], p["lon"]) if p["lat"] is not None else None
        if place and place.get("city"):
            cities[place["city"]] += 1
    title = (names.most_common(1)[0][0] if names else "") or (cities.most_common(1)[0][0] if cities else "")
    return title, countries


def build(index, config=None, manual=None, language="fr", cached_place=None):
    """Liste des voyages, sorties et moments à placer, du plus récent au plus ancien."""
    if cached_place is None:
        from utils import geocode
        cached_place = geocode.cached
    manual = manual_places() if manual is None else manual
    points = _points(index, manual)
    home = find_home(points, config)
    trips = []
    for group in _split(points, home):
        if len(group) < MIN_PHOTOS:
            continue
        located = [p for p in group if p["lat"] is not None]
        start, end = group[0]["when"], group[-1]["when"]
        if located:
            lat = sum(p["lat"] for p in located) / len(located)
            lon = sum(p["lon"] for p in located) / len(located)
            distance = world.distance_km(home, (lat, lon)) if home else None
            kind = "trip" if distance is None or distance > TRIP_KM else "outing"
        else:
            lat = lon = distance = None
            kind = "unplaced"
        if kind != "trip" and (end - start).days > MAX_DAYS_AT_HOME:
            continue
        title, countries = _place_names(group, language, cached_place)
        if not title and kind == "trip":  # sans ville connue : les pays (une sortie garde « Sortie »)
            title = ", ".join(c["name"] for c in countries[:3])
        route, last = [], None
        for p in located:
            spot = (round(p["lat"], 3), round(p["lon"], 3))
            if spot != last:
                route.append(spot)
                last = spot
        middle = start + (end - start) / 2
        cover = max(group, key=lambda p: (_score(p["q"]), -abs((p["when"] - middle).total_seconds())))
        trips.append({
            "id": f"{start:%Y%m%d}-{hashlib.sha1(group[0]['key'].encode()).hexdigest()[:6]}",
            "kind": kind, "title": title, "countries": countries,
            "start": start.isoformat(timespec="minutes"), "end": end.isoformat(timespec="minutes"),
            "count": len(group), "located": len(located), "manual": any(p["how"] == "manual" for p in located),
            "lat": lat, "lon": lon, "distance_km": round(distance) if distance is not None else None,
            "route": route, "cover": cover["key"], "keys": [p["key"] for p in group],
        })
    trips.sort(key=lambda t: t["start"], reverse=True)
    return {"home": home, "trips": trips}


def memories(trips, today=None, window_days=3):
    """Voyages vécus un jour comme aujourd'hui, les années précédentes : [(voyage, nombre d'années)]."""
    today = today or date.today()
    found = []
    for trip in trips:
        if trip["kind"] != "trip":
            continue
        start, end = datetime.fromisoformat(trip["start"]).date(), datetime.fromisoformat(trip["end"]).date()
        for years in range(1, 31):
            try:
                then = today.replace(year=today.year - years)
            except ValueError:  # 29 février
                then = today.replace(year=today.year - years, day=28)
            if start - timedelta(days=window_days) <= then <= end + timedelta(days=window_days):
                found.append((trip, years))
                break
    return found


def by_year(trips):
    """Récapitulatif par année : {année: {"trips": [...], "countries": [...]}} (voyages seulement)."""
    years = {}
    for trip in trips:
        if trip["kind"] != "trip":
            continue
        entry = years.setdefault(int(trip["start"][:4]), {"trips": [], "countries": []})
        entry["trips"].append(trip)
        for country in trip["countries"]:
            if country["iso"] not in {c["iso"] for c in entry["countries"]}:
                entry["countries"].append(country)
    return years
