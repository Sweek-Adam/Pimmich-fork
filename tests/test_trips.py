"""Carte des voyages : regroupement en voyages / sorties / moments à placer, souvenirs, pays hors ligne, API, cartes."""
import gzip
import json
from datetime import date, datetime, timedelta

import pytest

from utils import trips, world

HOME = {"latitude": 48.85, "longitude": 2.35}  # Paris


def _index():
    index = {}
    start = datetime(2025, 3, 1, 9)
    for day in range(30):  # la vie de tous les jours à la maison : pas un « moment »
        index[f"gdrive/maison_{day}.jpg"] = {"date": (start + timedelta(days=day)).isoformat(), "lat": 48.86, "lon": 2.34, "q": {"b": 120, "s": 10}}
    lisbon = datetime(2025, 8, 12, 10)
    for i, (lat, lon) in enumerate([(38.72, -9.14), (38.71, -9.13), (40.2, -8.41), (41.15, -8.61)]):
        index[f"gdrive/lisbonne_{i}.jpg"] = {"date": (lisbon + timedelta(hours=20 * i)).isoformat(), "lat": lat, "lon": lon, "q": {"b": 120, "s": 10 + i, "shot": i == 3}}
    picnic = datetime(2025, 6, 1, 12)
    for i in range(3):  # une sortie à 20 km
        index[f"gdrive/vincennes_{i}.jpg"] = {"date": (picnic + timedelta(minutes=30 * i)).isoformat(), "lat": 48.83, "lon": 2.6}
    party = datetime(2024, 12, 24, 19)
    for i in range(4):  # sans position
        index[f"smartphone/noel_{i}.jpg"] = {"date": (party + timedelta(hours=i)).isoformat(), "lat": None, "lon": None}
    index["gdrive/sans_date.jpg"] = {"date": None, "lat": 1, "lon": 1}
    return index


def _cached(lat, lon):
    return {"city": "Lisbonne", "country": "Portugal"} if lat < 40 else {"city": "Porto", "country": "Portugal"} if 41 < lat < 42 else None


def test_grouping_and_kinds():
    data = trips.build(_index(), HOME, manual={}, cached_place=_cached)
    kinds = {t["kind"]: t for t in data["trips"]}
    assert set(kinds) == {"trip", "outing", "unplaced"} and len(data["trips"]) == 3
    trip = kinds["trip"]
    assert trip["count"] == 4 and trip["title"] == "Lisbonne" and trip["countries"][0]["iso"] == "PT"
    assert trip["cover"] == "gdrive/lisbonne_2.jpg"  # la plus nette, sans la capture d'écran
    assert trip["route"][0] == (38.72, -9.14) and trip["route"][-1] == (41.15, -8.61) and trip["distance_km"] > 1000
    assert kinds["outing"]["count"] == 3 and kinds["outing"]["title"] == "" and kinds["unplaced"]["lat"] is None
    assert [t["start"][:4] for t in data["trips"]] == ["2025", "2025", "2024"]  # du plus récent au plus ancien
    assert tuple(data["home"]) == (48.85, 2.35)


def test_home_from_photos_without_frame_location():
    data = trips.build(_index(), {}, manual={}, cached_place=lambda *a: None)
    assert data["home"] == (48.75, 2.25)  # endroit le plus photographié
    assert {t["kind"] for t in data["trips"]} == {"trip", "outing", "unplaced"}


def test_manual_place(monkeypatch, tmp_path):
    monkeypatch.setattr(trips, "PLACES_FILE", tmp_path / "places.json")
    index = _index()
    unplaced = next(t for t in trips.build(index, HOME, cached_place=lambda *a: None)["trips"] if t["kind"] == "unplaced")
    trips.set_place(unplaced["keys"], 45.76, 4.84, "Chez Mamie")
    placed = next(t for t in trips.build(index, HOME, cached_place=lambda *a: None)["trips"] if t["start"] == unplaced["start"])
    assert placed["kind"] == "trip" and placed["title"] == "Chez Mamie" and placed["manual"] and placed["countries"][0]["iso"] == "FR"
    with pytest.raises(ValueError):
        trips.set_place(unplaced["keys"], 120, 4, "")
    trips.clear_place(unplaced["keys"])
    assert json.loads((tmp_path / "places.json").read_text()) == {}


def test_memories_and_years():
    data = trips.build(_index(), HOME, manual={}, cached_place=_cached)
    found = trips.memories(data["trips"], today=date(2026, 8, 14))
    assert len(found) == 1 and found[0][1] == 1 and found[0][0]["title"] == "Lisbonne"
    assert trips.memories(data["trips"], today=date(2026, 9, 30)) == []
    years = trips.by_year(data["trips"])
    assert list(years) == [2025] and years[2025]["countries"][0]["iso"] == "PT"


def test_world_offline():
    assert world.country_at(48.85, 2.35)["iso"] == "FR"
    assert world.country_at(35.68, 139.7)["iso"] == "JP"
    assert world.country_at(45.0, -30.0) is None  # en plein Atlantique
    assert world.country_name(world.country_at(52.52, 13.4), "de") == "Deutschland"
    assert 340 < world.distance_km((48.85, 2.35), (51.5, -0.12)) < 350


@pytest.fixture
def trips_env(monkeypatch, tmp_path, app_module):
    from web import routes_trips
    from utils import photo_index
    prepared = tmp_path / "prepared"
    for key in _index():
        (prepared / key).parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        Image.new("RGB", (64, 48), (120, 160, 200)).save(prepared / key)
    monkeypatch.setattr(photo_index, "load", _index)
    monkeypatch.setattr(trips, "PLACES_FILE", tmp_path / "places.json")
    monkeypatch.setattr(routes_trips, "PREPARED_DIR", prepared)
    monkeypatch.setattr(routes_trips, "_cache", {"key": None, "data": None})
    config = routes_trips.load_config()
    saved = {k: config.get(k) for k in ("latitude", "longitude", "trip_cards", "display_sources", "geocode_enabled")}
    routes_trips.save_config(dict(config, latitude=48.85, longitude=2.35, geocode_enabled=False))
    yield routes_trips, prepared
    config = dict(routes_trips.load_config())
    for key, value in saved.items():
        if value is None:
            config.pop(key, None)
        else:
            config[key] = value
    routes_trips.save_config(config)


HEADERS = {"Sec-Fetch-Site": "same-origin"}


def test_trips_api(admin_client, trips_env, monkeypatch):
    routes_trips, _prepared = trips_env
    data = admin_client.get("/api/trips").get_json()
    assert data["success"] and len(data["trips"]) == 3 and data["visited"] == ["PT"]
    assert all("keys" not in t for t in data["trips"]) and data["trips"][0]["cover_url"].startswith("/static/prepared/")
    trip = next(t for t in data["trips"] if t["kind"] == "trip")
    detail = admin_client.get(f"/api/trips/{trip['id']}").get_json()
    assert len(detail["photos"]) == 4
    card = admin_client.get(f"/api/trips/{trip['id']}/card.jpg")
    assert card.status_code == 200 and card.data[:2] == b"\xff\xd8"
    unplaced = next(t for t in data["trips"] if t["kind"] == "unplaced")
    assert admin_client.get(f"/api/trips/{unplaced['id']}/card.jpg").status_code == 404
    r = admin_client.post(f"/api/trips/{unplaced['id']}/place", json={"name": "Noël"}, headers=HEADERS)
    assert r.status_code == 400  # pas encore d'endroit
    r = admin_client.post(f"/api/trips/{unplaced['id']}/place", json={"lat": 45.76, "lon": 4.84, "name": "Chez Mamie"}, headers=HEADERS)
    assert r.get_json()["success"]
    data = admin_client.get("/api/trips").get_json()
    assert any(t["title"] == "Chez Mamie" and t["kind"] == "trip" for t in data["trips"]) and data["visited"] == ["FR", "PT"]
    assert admin_client.get("/api/trips/inconnu").status_code == 404


def test_trip_play(admin_client, trips_env, monkeypatch):
    routes_trips, prepared = trips_env
    import web.routes_slideshow as slideshow
    started = []
    monkeypatch.setattr(slideshow, "start_photo_playlist", lambda pid: started.append(pid) or (True, "ok", 200))
    playlists = []
    monkeypatch.setattr(routes_trips, "load_playlists", lambda: list(playlists))
    monkeypatch.setattr(routes_trips, "save_playlists", lambda items: playlists.__init__(items))
    trip = next(t for t in admin_client.get("/api/trips").get_json()["trips"] if t["kind"] == "trip")
    assert admin_client.post(f"/api/trips/{trip['id']}/play", headers=HEADERS).get_json()["success"]
    assert started == [f"voyage_{trip['id']}"]
    photos = playlists[0]["photos"]
    assert photos[0] == f"voyages_recits/{trip['id']}.jpg" and (prepared / photos[0]).is_file()
    assert photos[1:] == [f"gdrive/lisbonne_{i}.jpg" for i in range(4)]  # dans l'ordre où elles ont été prises


def test_places_search_and_world(admin_client, trips_env):
    results = admin_client.get("/api/places/search?q=portu").get_json()["results"]
    assert results and results[0]["name"] == "Portugal"
    r = admin_client.get("/api/map/world.json", headers={"Accept-Encoding": "gzip"})
    assert r.headers["Content-Encoding"] == "gzip" and json.loads(gzip.decompress(r.data))["features"]


def test_refresh_cards(trips_env):
    routes_trips, prepared = trips_env
    config = dict(routes_trips.load_config(), trip_cards="all", display_width=640, display_height=360, display_sources=["gdrive"])
    names = routes_trips.refresh_cards(config, today=date(2026, 8, 13))
    assert any(n.startswith("souvenir_") for n in names) and any(n.startswith("voyage_") for n in names)
    assert any(n.startswith("annee_2025_") for n in names)
    assert all((prepared / "voyages" / n).is_file() for n in names)
    assert "voyages" in routes_trips.load_config()["display_sources"]
    config = dict(routes_trips.load_config(), trip_cards="off")
    assert routes_trips.refresh_cards(config) == [] and not list((prepared / "voyages").glob("*.jpg"))
    assert "voyages" not in routes_trips.load_config()["display_sources"]


def test_trips_settings_admin_only(user_client, admin_client, trips_env, monkeypatch):
    routes_trips, _prepared = trips_env
    monkeypatch.setattr(routes_trips, "refresh_cards", lambda config: None)
    assert user_client.post("/api/trips/settings", json={"cards": "all"}, headers=HEADERS).status_code in (302, 403)
    assert admin_client.post("/api/trips/settings", json={"cards": "memories", "osm_tiles": True}, headers=HEADERS).get_json()["success"]
    config = routes_trips.load_config()
    assert config["trip_cards"] == "memories" and config["map_osm_tiles"] is True
    routes_trips.save_config(dict(config, map_osm_tiles=False))


def test_trips_home(admin_client, user_client, trips_env):
    routes_trips, _prepared = trips_env
    assert admin_client.post("/api/trips/home", json={"lat": "x"}, headers=HEADERS).status_code == 400
    assert user_client.post("/api/trips/home", json={"lat": 1, "lon": 2}, headers=HEADERS).status_code in (302, 403)
    assert admin_client.post("/api/trips/home", json={"lat": 38.7223, "lon": -9.1393}, headers=HEADERS).get_json()["success"]
    config = routes_trips.load_config()
    assert (config["latitude"], config["longitude"]) == (38.722, -9.139)
    data = admin_client.get("/api/trips").get_json()
    assert data["home"] == [38.722, -9.139] and "PT" not in data["visited"]  # Lisbonne, c'est la maison maintenant
