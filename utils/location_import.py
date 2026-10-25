"""
Retrouver le lieu des photos qui n'ont pas de coordonnées GPS (téléphones qui les retirent au partage) :
  - chronologie Google Maps (export du téléphone : Timeline.json ; ancien Takeout : Records.json, Semantic Location
    History) : pour chaque photo datée, l'endroit où vous étiez à cette heure-là (à 45 minutes près) ;
  - Google Takeout de Google Photos : les fichiers .json à côté des photos gardent leur lieu (geoData).
Les lieux trouvés sont gardés dans cache/photo_locations.json et complètent l'index des photos (carte, jeux,
légendes), sans toucher aux fichiers des photos.
"""
import io
import json
import os
import re
import time
import zipfile
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

LOCATIONS_FILE = Path(__file__).resolve().parent.parent / "cache" / "photo_locations.json"
MAX_GAP = 45 * 60          # secondes : point de la chronologie le plus proche accepté
DEGREES = re.compile(r"(-?\d+(?:\.\d+)?)°?,\s*(-?\d+(?:\.\d+)?)°?")


def load_locations():
    try:
        return json.loads(LOCATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_locations(data):
    LOCATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCATIONS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, LOCATIONS_FILE)


def merge_into(index):
    """Complète l'index des photos avec les lieux importés (seulement là où il n'y a pas de coordonnées)."""
    places = load_locations()
    for key, place in places.items():
        entry = index.get(key)
        if entry is not None and entry.get("lat") is None:
            entry["lat"], entry["lon"], entry["place_from"] = place["lat"], place["lon"], place.get("how")
    return index


# --- Lecture des exports ---

def _ts(value):
    """Horodatage (ISO avec fuseau, millisecondes ou secondes) -> secondes UTC, sinon None."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or str(value).isdigit():
        number = float(value)
        return number / 1000 if number > 1e11 else number
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.timestamp()


def _latlng(value):
    """« 48.8566°, 2.3522° » ou {latitudeE7, longitudeE7} ou {latitude, longitude} -> (lat, lon)."""
    if isinstance(value, str):
        match = DEGREES.search(value)
        return (float(match.group(1)), float(match.group(2))) if match else None
    if isinstance(value, dict):
        if "latitudeE7" in value and "longitudeE7" in value:
            return value["latitudeE7"] / 1e7, value["longitudeE7"] / 1e7
        if "latitude" in value and "longitude" in value:
            return float(value["latitude"]), float(value["longitude"])
        for key in ("latLng", "LatLng", "point", "placeLocation", "location"):
            if key in value:
                return _latlng(value[key])
    return None


def timeline_points(data):
    """Points (secondes UTC, lat, lon) d'une chronologie Google, quel que soit le format d'export."""
    points = []

    def add(when, where):
        when, where = _ts(when), _latlng(where)
        if when and where and abs(where[0]) <= 90 and abs(where[1]) <= 180 and where != (0.0, 0.0):
            points.append((when, where[0], where[1]))

    if isinstance(data, list):  # export iPhone : liste de segments
        data = {"semanticSegments": data}
    for item in (data or {}).get("locations", []):  # Records.json
        add(item.get("timestamp") or item.get("timestampMs"), item)
    for segment in (data or {}).get("semanticSegments", []):  # Timeline.json (export du téléphone)
        for point in segment.get("timelinePath", []):
            add(point.get("time"), point.get("point"))
        visit = (segment.get("visit") or {}).get("topCandidate", {}).get("placeLocation")
        if visit:
            for when in (segment.get("startTime"), segment.get("endTime")):
                add(when, visit)
            start, end = _ts(segment.get("startTime")), _ts(segment.get("endTime"))
            if start and end and end - start > MAX_GAP:  # longue visite : un point toutes les 30 minutes
                for when in range(int(start), int(end), 1800):
                    add(when, visit)
        activity = segment.get("activity") or {}
        add(segment.get("startTime"), activity.get("start"))
        add(segment.get("endTime"), activity.get("end"))
    for signal in (data or {}).get("rawSignals", []):
        position = signal.get("position") or {}
        add(position.get("timestamp"), position.get("LatLng") or position.get("latLng"))
    for item in (data or {}).get("timelineObjects", []):  # Semantic Location History (ancien Takeout)
        visit = item.get("placeVisit")
        if visit:
            duration = visit.get("duration") or {}
            for key in ("startTimestamp", "endTimestamp", "startTimestampMs", "endTimestampMs"):
                add(duration.get(key), visit.get("location"))
        segment = item.get("activitySegment")
        if segment:
            duration = segment.get("duration") or {}
            add(duration.get("startTimestamp") or duration.get("startTimestampMs"), segment.get("startLocation"))
            add(duration.get("endTimestamp") or duration.get("endTimestampMs"), segment.get("endLocation"))
    return sorted(points)


def takeout_places(data):
    """Fichier .json de Google Takeout (Google Photos) : (nom de la photo, moment UTC, lat, lon), sinon None."""
    if not isinstance(data, dict) or "title" not in data:
        return None
    for key in ("geoData", "geoDataExif"):
        where = _latlng(data.get(key) or {})
        if where and where != (0.0, 0.0):
            taken = _ts((data.get("photoTakenTime") or {}).get("timestamp"))
            return data["title"], taken, where[0], where[1]
    return None


def read_upload(name, content):
    """Fichier envoyé (.json ou .zip de Takeout) -> (points de chronologie, lieux Takeout)."""
    points, places = [], []

    def handle(filename, raw):
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            return
        found = takeout_places(data)
        if found:
            places.append(found)
        else:
            points.extend(timeline_points(data))

    if name.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                if info.filename.lower().endswith(".json") and info.file_size < 300 * 1024 * 1024:
                    handle(info.filename, archive.read(info))
    else:
        handle(name, content)
    return points, places


# --- Rapprochement avec les photos ---

def _photo_time(entry):
    """Moment de la prise de vue en secondes UTC (date de la photo, à l'heure locale du cadre)."""
    try:
        return time.mktime(datetime.fromisoformat(entry["date"]).timetuple())
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _stem(name):
    return re.sub(r"\(\d+\)$", "", Path(str(name)).stem).lower()


def match(index, points, places, existing=None):
    """Lieux trouvés pour les photos sans coordonnées : {clé: {lat, lon, how}} (les déjà connus sont gardés)."""
    found = dict(existing or {})
    by_name = {}
    for title, taken, lat, lon in places:
        by_name.setdefault(_stem(title), []).append((taken, lat, lon))
    times = [p[0] for p in points]
    for key, entry in index.items():
        if entry.get("lat") is not None or key in found:
            continue
        stem = _stem(key.split("/", 1)[-1])
        candidates = by_name.get(stem) or next((v for s, v in by_name.items() if stem.startswith(s + "_")), None)
        when = _photo_time(entry)
        if candidates:  # même nom de fichier dans Takeout (le plus proche dans le temps s'il y en a plusieurs)
            taken, lat, lon = min(candidates, key=lambda c: abs((c[0] or 0) - (when or 0)))
            found[key] = {"lat": lat, "lon": lon, "how": "takeout"}
            continue
        if when is None or not points:
            continue
        i = bisect_left(times, when)
        best = min((points[j] for j in (i - 1, i) if 0 <= j < len(points)), key=lambda p: abs(p[0] - when))
        if abs(best[0] - when) <= MAX_GAP:
            found[key] = {"lat": round(best[1], 6), "lon": round(best[2], 6), "how": "timeline"}
    return found


def import_files(files, index):
    """Lit les exports envoyés et enregistre les lieux trouvés. Retourne un bilan."""
    points, places = [], []
    for name, content in files:
        p, l = read_upload(name, content)
        points += p
        places += l
    points.sort()
    before = load_locations()
    found = match(index, points, places, before)
    save_locations(found)
    without = sum(1 for k, e in index.items() if e.get("lat") is None and k not in found)
    return {"points": len(points), "takeout": len(places), "added": len(found) - len(before), "located": len(found), "without": without}
