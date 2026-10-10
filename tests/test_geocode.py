"""Nom des lieux (OpenStreetMap) : désactivé par défaut, une requête par lieu, cache."""
import pytest

from utils import geocode


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(geocode, "CACHE_FILE", tmp_path / "places.json")
    monkeypatch.setattr(geocode.time, "sleep", lambda s: None)


def test_one_request_per_place(monkeypatch):
    calls = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"address": {"town": "Annecy", "country": "France"}}
    monkeypatch.setattr(geocode.requests, "get", lambda url, **k: calls.append(k["params"]) or Resp())
    index = {"a.jpg": {"lat": 45.8992, "lon": 6.1294}, "b.jpg": {"lat": 45.9011, "lon": 6.1301}, "c.jpg": {"lat": None, "lon": None}}
    assert geocode.fill_places(index) == 1  # deux photos au même endroit : une seule requête
    assert geocode.cached(45.9, 6.13) == {"city": "Annecy", "country": "France"}
    assert geocode.fill_places(index) == 0 and len(calls) == 1
    assert calls[0]["lat"] == 45.8992  # précision limitée envoyée


def test_network_error_is_retried_later(monkeypatch):
    def fail(*a, **k):
        raise geocode.requests.ConnectionError()
    monkeypatch.setattr(geocode.requests, "get", fail)
    assert geocode.lookup(48.85, 2.35) is None and geocode.cached(48.85, 2.35) is None


def test_slideshow_metadata_uses_cached_place(monkeypatch):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pytest.importorskip("pygame")
    import local_slideshow as ls
    monkeypatch.setattr(ls, "get_photo_metadata", lambda path: {})
    monkeypatch.setattr(ls.photo_index, "info", lambda path, index=None: {"date": "2024-07-14T10:00:00", "lat": 45.8992, "lon": 6.1294})
    geocode.CACHE_FILE.write_text('{"45.90,6.13": {"city": "Annecy", "country": "France"}}')
    meta = ls.display_metadata("/static/prepared/gdrive/x.jpg")
    assert meta["city"] == "Annecy" and meta["dateTimeOriginal"] == "2024-07-14T10:00:00"
