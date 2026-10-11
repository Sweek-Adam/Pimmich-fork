"""
Albums intelligents : « Été 2025 », « Noël en famille », « Les enfants »... Un album intelligent est une playlist
définie par des règles (période de l'année, années, personnes, sources, lieu, favoris) : ses photos sont
recalculées automatiquement à chaque nouvelle photo préparée. Le cadre suggère aussi des albums d'après la
bibliothèque (étés, Noëls, lieux souvent photographiés).
"""
import re
import threading
from datetime import date
from pathlib import Path

from utils.message_renderer import N_

BASE_DIR = Path(__file__).resolve().parent.parent
PREPARED_DIR = BASE_DIR / "static" / "prepared"
SKIP_SOURCES = {"messages", "compositions"}
VIDEO_EXT = (".mp4", ".mov", ".avi", ".mkv")
PREFIX = "smart-"
MIN_SUGGESTED = 8
_lock = threading.Lock()

# Périodes de l'année (jour-mois) ; une période à cheval sur deux années compte pour l'année où elle commence
EVENTS = {
    "summer": {"label": N_("Été"), "from": "06-21", "to": "09-22", "icon": "fa-sun"},
    "autumn": {"label": N_("Automne"), "from": "09-23", "to": "12-20", "icon": "fa-leaf"},
    "winter": {"label": N_("Hiver"), "from": "12-21", "to": "03-19", "icon": "fa-snowflake"},
    "spring": {"label": N_("Printemps"), "from": "03-20", "to": "06-20", "icon": "fa-seedling"},
    "christmas": {"label": N_("Noël"), "from": "12-20", "to": "01-02", "icon": "fa-gifts"},
    "halloween": {"label": N_("Halloween"), "from": "10-25", "to": "11-01", "icon": "fa-ghost"},
    "valentine": {"label": N_("Saint-Valentin"), "from": "02-13", "to": "02-15", "icon": "fa-heart"},
}
DAY = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def clean_rules(rules):
    """Règles validées : {from, to, years, people, people_all, sources, favorites, place, media}."""
    rules = rules if isinstance(rules, dict) else {}
    clean = {}
    if DAY.match(str(rules.get("from", ""))) and DAY.match(str(rules.get("to", ""))):
        clean["from"], clean["to"] = rules["from"], rules["to"]
    years = sorted({int(y) for y in rules.get("years") or [] if str(y).isdigit() and 1900 <= int(y) <= 2200})
    if years:
        clean["years"] = years
    for key in ("people", "sources"):
        values = sorted({str(v).strip()[:80] for v in rules.get(key) or [] if str(v).strip()})[:50]
        if values:
            clean[key] = values
    if clean.get("people") and rules.get("people_all"):
        clean["people_all"] = True
    if rules.get("favorites"):
        clean["favorites"] = True
    place = str(rules.get("place") or "").strip()[:80]
    if place:
        clean["place"] = place
    if rules.get("media") in ("photos", "videos"):
        clean["media"] = rules["media"]
    return clean


def _in_period(day, rules):
    """(dans la période, année de la période) pour une date ; année = celle où la période commence."""
    if "from" not in rules:
        return True, day.year
    start, end, now = rules["from"], rules["to"], day.strftime("%m-%d")
    if start <= end:
        return start <= now <= end, day.year
    if now >= start:
        return True, day.year
    return now <= end, day.year - 1


def matches(item, rules):
    if rules.get("media") == "photos" and item["video"] or rules.get("media") == "videos" and not item["video"]:
        return False
    if rules.get("favorites") and not item["favorite"]:
        return False
    if rules.get("sources") and item["source"] not in rules["sources"]:
        return False
    if rules.get("people"):
        present = set(item["people"])
        wanted = set(rules["people"])
        if not (wanted <= present if rules.get("people_all") else wanted & present):
            return False
    if rules.get("place") and rules["place"].lower() not in (item["place"] or "").lower():
        return False
    if "from" in rules or rules.get("years"):
        if not item["date"]:
            return False
        day = date.fromisoformat(item["date"][:10])
        inside, year = _in_period(day, rules)
        if not inside or (rules.get("years") and year not in rules["years"]):
            return False
    return True


def library(favorites=()):
    """Toutes les photos et vidéos préparées : [{path, source, date, video, favorite, people, place}]."""
    from utils import geocode, people, photo_index
    index, who, favorites = photo_index.load(), people.by_photo(), set(favorites)
    places = geocode._load()
    items = []
    for source in sorted(PREPARED_DIR.iterdir()) if PREPARED_DIR.is_dir() else []:
        if not source.is_dir() or source.name in SKIP_SOURCES or source.name.startswith("."):
            continue
        for f in sorted(source.iterdir()):
            if not f.is_file() or f.stem.endswith(("_polaroid", "_thumbnail", "_postcard")):
                continue
            video = f.suffix.lower() in VIDEO_EXT
            if not video and f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            rel = f"{source.name}/{f.name}"
            info = index.get(rel) or {}
            place = None
            if info.get("lat") is not None and info.get("lon") is not None:
                found = places.get(geocode._key(info["lat"], info["lon"])) or {}
                place = ", ".join(p for p in (found.get("city"), found.get("country")) if p) or None
            items.append({"path": rel, "source": source.name, "date": info.get("date"), "video": video,
                          "favorite": rel in favorites, "people": who.get(rel, []), "place": place})
    return items


def select(items, rules):
    """Photos d'un album, de la plus ancienne à la plus récente (l'ordre d'un souvenir)."""
    chosen = [i for i in items if matches(i, rules)]
    chosen.sort(key=lambda i: (i["date"] or "9999", i["path"]))
    return [i["path"] for i in chosen]


def suggestions(items, existing_names=()):
    """Albums proposés : chaque été / Noël / Halloween avec assez de photos, Noëls de toutes les années, lieux fréquents."""
    existing = {n.lower() for n in existing_names}
    found = []
    for key in ("summer", "christmas", "halloween"):
        event = EVENTS[key]
        per_year = {}
        for item in items:
            if item["date"]:
                inside, year = _in_period(date.fromisoformat(item["date"][:10]), event)
                if inside:
                    per_year[year] = per_year.get(year, 0) + 1
        for year, count in per_year.items():
            if count >= MIN_SUGGESTED:
                found.append({"event": key, "year": year, "count": count, "icon": event["icon"],
                              "rules": {"from": event["from"], "to": event["to"], "years": [year]}})
        if key == "christmas" and len([c for c in per_year.values() if c >= max(2, MIN_SUGGESTED // 2)]) >= 2:
            found.append({"event": "christmas_all", "count": sum(per_year.values()), "icon": event["icon"],
                          "rules": {"from": event["from"], "to": event["to"]}})
    places = {}
    for item in items:
        if item["place"]:
            city = item["place"].split(",")[0].strip()
            places[city] = places.get(city, 0) + 1
    for city, count in sorted(places.items(), key=lambda kv: -kv[1])[:5]:
        if count >= MIN_SUGGESTED * 2:
            found.append({"event": "place", "place": city, "count": count, "icon": "fa-map-marker-alt", "rules": {"place": city}})
    found.sort(key=lambda s: (-(s.get("year") or 0), -s["count"]))
    return [s for s in found if s.get("name", "").lower() not in existing][:12]


def refresh(load_playlists, save_playlists, favorites=()):
    """Recalcule les photos de tous les albums intelligents ; renvoie le nombre d'albums mis à jour."""
    with _lock:
        playlists = load_playlists()
        smart = [p for p in playlists if isinstance(p.get("smart"), dict)]
        if not smart:
            return 0
        items = library(favorites)
        changed = 0
        for playlist in smart:
            photos = select(items, clean_rules(playlist["smart"]))
            if photos != playlist.get("photos"):
                playlist["photos"] = photos
                changed += 1
        if changed:
            save_playlists(playlists)
        return changed
