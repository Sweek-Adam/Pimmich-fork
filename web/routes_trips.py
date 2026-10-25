"""
Carte des voyages : où les photos ont été prises, regroupées en voyages et sorties ; moments à situer à la main ;
cartes dessinées pour le cadre (voyage, souvenir « il y a un an », récapitulatif de l'année) ; histoire d'un voyage
(sa carte puis ses photos dans l'ordre) lancée sur le cadre.
Fond de carte hors ligne par défaut ; OpenStreetMap (tuiles, recherche de lieux) seulement si on l'active.
"""
import gzip
import hashlib
import io

from babel.dates import format_date as babel_format_date, format_skeleton
from flask import make_response, send_file
from flask_babel import force_locale, get_locale

from web.core import *  # noqa: F401,F403 (application, constantes et utilitaires partagés)
from web.core import _
from utils import geocode, layout_engine, photo_index, sky, trip_map, trips, world

SOURCE = "voyages"            # cartes ajoutées au diaporama
STORY_SOURCE = "voyages_recits"  # cartes d'ouverture des histoires (jamais dans le diaporama normal)
PLAYLIST_PREFIX = "voyage_"
CARD_MODES = ("off", "memories", "all")
_cache = {"key": None, "data": None}
_world_gz = []


def _mtime(path):
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0


def current(config=None):
    """Voyages et sorties (recalculés seulement si l'index, les lieux ou la position du cadre ont changé)."""
    config = config or load_config()
    language = (config.get("language") or "fr")[:2]
    key = (_mtime(photo_index.INDEX_FILE), _mtime(trips.PLACES_FILE), _mtime(geocode.CACHE_FILE), _mtime(sky.LOCATION_FILE),
           language, config.get("latitude"), config.get("longitude"))
    if _cache["key"] != key:
        _cache["data"] = trips.build(photo_index.load(), config, language=language)
        _cache["key"] = key
    return _cache["data"]


def _find(trip_id):
    return next((t for t in current()["trips"] if t["id"] == trip_id), None)


# --- Textes (dans la langue de l'interface ou du cadre) ---

def _locale():
    return str(get_locale() or "fr")


def date_range(trip):
    start, end = datetime.fromisoformat(trip["start"]).date(), datetime.fromisoformat(trip["end"]).date()
    locale = _locale()
    if start == end:
        return babel_format_date(start, "long", locale=locale)
    if start.year == end.year:
        return f"{format_skeleton('MMMMd', start, locale=locale)} – {babel_format_date(end, 'long', locale=locale)}"
    return f"{babel_format_date(start, 'long', locale=locale)} – {babel_format_date(end, 'long', locale=locale)}"


def title_of(trip):
    if trip.get("title"):
        return trip["title"]
    return _("Moment à placer") if trip["kind"] == "unplaced" else _("Sortie")


def card_lines(trip):
    details = [_("%(count)s photos", count=trip["count"])] + [c["name"] for c in trip.get("countries") or []][:3]
    return [date_range(trip), " · ".join(details)]


def _photo_paths(trip, count=3):
    """Quelques photos du voyage pour sa carte : la plus belle, puis réparties dans le temps."""
    keys = [k for k in trip["keys"] if Path(k).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not keys:
        return []
    chosen = [trip["cover"]] if trip["cover"] in keys else []
    for i in range(1, count + 1):
        key = keys[min(len(keys) - 1, len(keys) * i // (count + 1))]
        if key not in chosen:
            chosen.append(key)
    return [PREPARED_DIR / k for k in chosen[:count] if (PREPARED_DIR / k).is_file()]


def render_trip_card(trip, width, height, banner="", home=None):
    return trip_map.card(width, height, trip, _photo_paths(trip), title_of(trip), card_lines(trip), banner, home)


def render_year_card(year, entry, width, height, home=None):
    lines = [" · ".join([_("%(count)s voyage(s)", count=len(entry["trips"])), _("%(count)s pays", count=len(entry["countries"]))])]
    if entry["countries"]:
        lines.append(", ".join(c["name"] for c in entry["countries"][:8]))
    return trip_map.year_card(width, height, entry["trips"], _("Nos voyages en %(year)s", year=year), lines, home)


# --- Cartes du diaporama ---

def refresh_cards(config=None, today=None):
    """Prépare les cartes de la source « voyages » selon le réglage ; renvoie leurs noms."""
    config = dict(config or load_config())
    mode = config.get("trip_cards", "off")
    folder = PREPARED_DIR / SOURCE
    wanted = {}
    with app.app_context(), force_locale(config.get("language") or "fr"):
        if mode in ("memories", "all"):
            data = current(config)
            width, height = int(config.get("display_width", 1920)), int(config.get("display_height", 1080))
            for trip, years in trips.memories(data["trips"], today):
                banner = _("Il y a un an") if years == 1 else _("Il y a %(count)s ans", count=years)
                wanted[f"souvenir_{trip['id']}.jpg"] = lambda t=trip, b=banner: render_trip_card(t, width, height, b, data["home"])
            if mode == "all":
                for trip in data["trips"]:
                    if trip["kind"] == "trip":
                        wanted[f"voyage_{trip['id']}.jpg"] = lambda t=trip: render_trip_card(t, width, height, "", data["home"])
                for year, entry in trips.by_year(data["trips"]).items():
                    signature = hashlib.sha1("-".join(sorted(t["id"] for t in entry["trips"])).encode()).hexdigest()[:6]
                    wanted[f"annee_{year}_{signature}.jpg"] = \
                        lambda y=year, e=entry: render_year_card(y, e, width, height, data["home"])
        folder.mkdir(parents=True, exist_ok=True)
        size_tag = f"{config.get('display_width')}x{config.get('display_height')}-{config.get('language')}"
        stamp = folder / ".size"
        resize = not stamp.exists() or stamp.read_text() != size_tag
        for name, render in wanted.items():
            target = folder / name
            if target.exists() and not resize:
                continue
            image = render()
            tmp = folder / f".{name}"
            image.save(tmp, "JPEG", quality=88)
            tmp.replace(target)
        stamp.write_text(size_tag)
    for old in folder.glob("*.jpg"):
        if old.name not in wanted:
            old.unlink(missing_ok=True)
    sources = list(config.get("display_sources") or [])
    if (mode != "off") != (SOURCE in sources):
        config["display_sources"] = [s for s in sources if s != SOURCE] + ([SOURCE] if mode != "off" else [])
        save_config(config)
    return sorted(wanted)


# --- API ---

def _public(trip):
    cover = trip["cover"]
    if Path(cover).suffix.lower() in VIDEO_EXTENSIONS:
        cover = f"{Path(cover).parent}/{Path(cover).stem}_thumbnail.jpg"
    return {**{k: v for k, v in trip.items() if k != "keys"}, "title": title_of(trip), "dates": date_range(trip),
            "cover_url": url_for("static", filename=f"prepared/{cover}")}


@app.route('/api/trips', methods=['GET'])
@login_required
def trips_api():
    config = load_config()
    data = current(config)
    by_year = {year: {"trips": len(e["trips"]), "countries": [c["name"] for c in e["countries"]]}
               for year, e in trips.by_year(data["trips"]).items()}
    visited = sorted({c["iso"] for t in data["trips"] if t["kind"] == "trip" for c in t["countries"] if c["iso"]})
    memories = [{"id": t["id"], "years": y} for t, y in trips.memories(data["trips"])]
    return jsonify({"success": True, "home": data["home"], "trips": [_public(t) for t in data["trips"]],
                    "years": by_year, "visited": visited, "memories": memories,
                    "settings": {"cards": config.get("trip_cards", "off"), "osm_tiles": bool(config.get("map_osm_tiles")),
                                 "search": bool(config.get("geocode_enabled"))}})


@app.route('/api/trips/<trip_id>', methods=['GET'])
@login_required
def trip_detail_api(trip_id):
    trip = _find(trip_id)
    if trip is None:
        return jsonify({"success": False, "message": _("Voyage introuvable.")}), 404
    photos = []
    for key in trip["keys"]:
        thumb = f"{Path(key).parent}/{Path(key).stem}_thumbnail.jpg" if Path(key).suffix.lower() in VIDEO_EXTENSIONS else key
        photos.append({"path": key, "thumb": url_for("static", filename=f"prepared/{thumb}")})
    return jsonify({"success": True, "trip": _public(trip), "photos": photos})


@app.route('/api/trips/<trip_id>/place', methods=['POST', 'DELETE'])
@login_required
def trip_place_api(trip_id):
    """Situe un moment (ou renomme un voyage) ; DELETE : oublie les positions et noms donnés à la main."""
    trip = _find(trip_id)
    if trip is None:
        return jsonify({"success": False, "message": _("Voyage introuvable.")}), 404
    if request.method == 'DELETE':
        trips.clear_place(trip["keys"])
        return jsonify({"success": True, "message": _("Position retirée.")})
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()[:80]
    try:
        lat = float(data["lat"]) if data.get("lat") is not None else trip["lat"]
        lon = float(data["lon"]) if data.get("lon") is not None else trip["lon"]
        if lat is None or lon is None:
            raise ValueError
        trips.set_place(trip["keys"], lat, lon, name)
    except (KeyError, TypeError, ValueError):
        return jsonify({"success": False, "message": _("Choisissez un endroit sur la carte.")}), 400
    return jsonify({"success": True, "message": _("C'est noté : la carte est à jour.")})


@app.route('/api/trips/<trip_id>/card.jpg', methods=['GET'])
@login_required
def trip_card_api(trip_id):
    trip = _find(trip_id)
    if trip is None or trip["lat"] is None:
        abort(404)
    image = render_trip_card(trip, 960, 540, home=current()["home"])
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    buffer.seek(0)
    return send_file(buffer, mimetype="image/jpeg", max_age=0)


@app.route('/api/trips/<trip_id>/play', methods=['POST'])
@login_required
def trip_play_api(trip_id):
    """L'histoire du voyage sur le cadre : sa carte, puis ses photos dans l'ordre où elles ont été prises."""
    from web.routes_slideshow import start_photo_playlist
    trip = _find(trip_id)
    if trip is None:
        return jsonify({"success": False, "message": _("Voyage introuvable.")}), 404
    config = load_config()
    photos = [k for k in trip["keys"] if (PREPARED_DIR / k).is_file()]
    if trip["lat"] is not None:
        folder = PREPARED_DIR / STORY_SOURCE
        folder.mkdir(parents=True, exist_ok=True)
        render_trip_card(trip, int(config.get("display_width", 1920)), int(config.get("display_height", 1080)),
                         home=current(config)["home"]).save(folder / f"{trip_id}.jpg", "JPEG", quality=88)
        photos.insert(0, f"{STORY_SOURCE}/{trip_id}.jpg")
    playlists = [p for p in load_playlists() if not str(p.get("id", "")).startswith(PLAYLIST_PREFIX)]  # une seule histoire gardée
    playlist_id = f"{PLAYLIST_PREFIX}{trip_id}"
    playlists.append({"id": playlist_id, "name": _("Voyage : %(title)s", title=title_of(trip)), "photos": photos,
                      "music_file": None, "layout": layout_engine.UNIQUE})
    save_playlists(playlists)
    ok, message, status = start_photo_playlist(playlist_id)
    return jsonify({"success": ok, "message": _("L'histoire du voyage commence sur le cadre.") if ok else message}), status


@app.route('/api/trips/settings', methods=['POST'])
@admin_required
def trips_settings_api():
    data = request.get_json(silent=True) or {}
    config = dict(load_config())
    if data.get("cards") in CARD_MODES:
        config["trip_cards"] = data["cards"]
    if "osm_tiles" in data:
        config["map_osm_tiles"] = bool(data["osm_tiles"])
    save_config(config)
    threading.Thread(target=refresh_cards, args=(config,), daemon=True, name="trip-cards").start()
    return jsonify({"success": True, "message": _("Réglages de la carte enregistrés.")})


@app.route('/api/places/search', methods=['GET'])
@login_required
def places_search_api():
    """Recherche d'un lieu : les pays hors ligne, et (si le géocodage est activé) OpenStreetMap."""
    query = str(request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"success": True, "results": []})
    config = load_config()
    language = (config.get("language") or "fr")[:2]
    lowered = query.lower()
    results = []
    for country in world.countries():
        name = world.country_name(country, language)
        if name and lowered in name.lower():
            x0, y0, x1, y1 = country["bbox"]
            results.append({"name": name, "lat": (y0 + y1) / 2, "lon": (x0 + x1) / 2, "bbox": [y0, x0, y1, x1]})
    results = results[:5]
    if config.get("geocode_enabled"):
        results = geocode.search(query, language) + results
    return jsonify({"success": True, "results": results[:10]})


@app.route('/api/map/world.json', methods=['GET'])
@login_required
def world_map_api():
    """Fond de carte hors ligne (contours des pays), compressé une fois pour toutes."""
    if not _world_gz:
        _world_gz.append(gzip.compress(world.WORLD_FILE.read_bytes(), 6))
    if "gzip" in (request.headers.get("Accept-Encoding") or ""):
        response = make_response(_world_gz[0])
        response.headers["Content-Encoding"] = "gzip"
    else:
        response = make_response(world.WORLD_FILE.read_bytes())
    response.headers["Content-Type"] = "application/json"
    response.headers["Cache-Control"] = "private, max-age=86400"
    response.headers["Vary"] = "Accept-Encoding"
    return response


@app.route('/api/trips/home', methods=['POST'])
@admin_required
def trips_home_api():
    """Position de la maison (= du cadre) : sépare voyages et sorties, et sert aussi au lever et coucher du soleil."""
    data = request.get_json(silent=True) or {}
    try:
        lat, lon = round(float(data["lat"]), 3), round(float(data["lon"]), 3)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify({"success": False, "message": _("Choisissez un endroit sur la carte.")}), 400
    save_config(dict(load_config(), latitude=lat, longitude=lon))
    return jsonify({"success": True, "message": _("Maison placée : voyages et sorties sont recalculés.")})


# --- Retrouver les lieux des photos sans GPS (chronologie Google Maps, Google Takeout) ---

@app.route('/api/locations', methods=['GET'])
@login_required
def locations_status_api():
    from utils import location_import, photo_index
    index = photo_index.load()
    photos = [e for k, e in index.items() if not k.lower().endswith((".mp4", ".mov"))]
    return jsonify({"success": True, "photos": len(photos), "with_place": sum(1 for e in photos if e.get("lat") is not None),
                    "imported": len(location_import.load_locations())})


@app.route('/api/locations/import', methods=['POST'])
@login_required
def locations_import_api():
    from utils import location_import, photo_index
    files = [(f.filename or "export.json", f.read()) for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"success": False, "message": _("Aucun fichier reçu.")}), 400
    try:
        result = location_import.import_files(files, photo_index.load())
    except Exception as e:
        return jsonify({"success": False, "message": _("Fichier illisible : %(error)s", error=str(e)[:120])}), 400
    if not result["points"] and not result["takeout"]:
        return jsonify({"success": False, "message": _("Aucun lieu dans ces fichiers (chronologie Google Maps ou Google Takeout attendus)."), **result}), 400
    _cache["key"] = None  # voyages recalculés avec les nouveaux lieux
    return jsonify({"success": True, **result,
                    "message": _("%(count)s photo(s) ont retrouvé leur lieu. Les noms des villes arrivent dans quelques minutes.", count=result["added"])})


@app.route('/api/locations', methods=['DELETE'])
@login_required
def locations_forget_api():
    from utils import location_import
    location_import.save_locations({})
    return jsonify({"success": True, "message": _("Lieux importés oubliés.")})
