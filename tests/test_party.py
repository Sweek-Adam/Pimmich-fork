"""Mode fête : QR code, photos des invités affichées aussitôt, Mur de la fête, retour au diaporama habituel."""
import io
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

from utils import party

SAME = {"Sec-Fetch-Site": "same-origin"}
NOW = datetime(2026, 11, 7, 19, 0)


def test_start_and_stop_restore_previous_settings():
    config = {"display_sources": ["gdrive", "immich"], "layout_override": "liege"}
    on = party.start(config, "  Les 40 ans   de Léa ", 5, only_party=True, now=NOW)
    assert party.active(on, NOW) and not party.active(on, NOW + timedelta(hours=6))
    assert on["party"]["name"] == "Les 40 ans de Léa" and on["party"]["source"] == "fete_20261107"
    assert on["display_sources"] == ["fete_20261107", "messages"] and on["layout_override"] == "fete"
    longer = party.start(on, "Les 40 ans de Léa", 3, only_party=True, now=NOW + timedelta(hours=4))  # prolonger
    assert longer["party"]["saved"]["display_sources"] == ["gdrive", "immich"] and longer["party"]["started"] == on["party"]["started"]
    off = party.stop(longer)
    assert off["display_sources"] == ["gdrive", "immich"] and off["layout_override"] == "liege" and not party.active(off)
    mixed = party.start(config, "", 2, only_party=False, now=NOW)
    assert mixed["display_sources"] == ["gdrive", "immich", "fete_20261107"] and mixed["party"]["name"] == "La fête"
    assert party.start(config, "x", 999, now=NOW)["party"]["until"] == (NOW + timedelta(hours=party.MAX_HOURS)).isoformat(timespec="minutes")


def test_live_arrivals_are_injected_once(tmp_path, monkeypatch):
    monkeypatch.setattr(party, "LIVE_FILE", tmp_path / "live.json")
    monkeypatch.setattr(party, "AUTHORS_FILE", tmp_path / "authors.json")
    photos = []
    for name in ("a", "b", "c", "new1", "new2"):
        path = tmp_path / f"{name}.jpg"
        path.write_bytes(b"x")
        photos.append(str(path))
    party.push_live(photos[3], "Léa")
    party.push_live(photos[4], "Tom")
    arrived = party.pop_live()
    assert [a["author"] for a in arrived] == ["Léa", "Tom"] and party.pop_live() == []
    playlist = party.inject(photos[:3] + [photos[3]], 1, [a["path"] for a in arrived])
    assert playlist == [photos[0], photos[4], photos[3], photos[1], photos[2]]   # la plus récente d'abord, sans doublon
    assert party.author_of(photos[4]) == "Tom" and party.author_of(photos[0]) is None


def test_party_wall_layout(monkeypatch):
    from utils import compositions as comp
    monkeypatch.setattr("utils.config_manager.load_config", lambda: {"party": {"active": True, "name": "Mariage de Zoé", "until": "2999-01-01T00:00"}})
    images = [Image.new("RGB", (400, 300), (40 * i, 100, 200)) for i in range(5)]
    image = party.party_wall(images, None, 960, 540, random.Random(1))
    assert image.size == (960, 540)
    assert "fete" in comp.FORMATS and comp.in_season("fete")
    monkeypatch.setattr("utils.config_manager.load_config", lambda: {})
    assert not comp.in_season("fete")   # hors fête : jamais proposé


@pytest.fixture()
def party_on(sandbox, monkeypatch, tmp_path):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    monkeypatch.setattr(party, "LIVE_FILE", tmp_path / "live.json")
    monkeypatch.setattr(party, "AUTHORS_FILE", tmp_path / "authors.json")
    yield original
    save_config(original)
    for d in Path("static/photos").glob("fete_*"):
        shutil.rmtree(d, ignore_errors=True)
    for d in Path("static/prepared").glob("fete_*"):
        shutil.rmtree(d, ignore_errors=True)


def test_party_api_and_guest_photo_shown_immediately(admin_client, client, party_on, monkeypatch):
    from web import routes_party, routes_guests
    monkeypatch.setattr(routes_party, "restart_slideshow_for_update", lambda *a, **k: None)
    r = admin_client.post("/api/party/start", json={"name": "Anniversaire", "hours": 4}, headers=SAME).get_json()
    assert r["success"] and r["active"] and r["name"] == "Anniversaire"
    page = client.get("/upload").get_data(as_text=True)
    assert "Anniversaire" in page
    # Un invité envoie une photo : préparée et ajoutée aux arrivées, sans validation ni redémarrage
    done = []
    monkeypatch.setattr(routes_guests.threading, "Thread", lambda target, args, **k: type("T", (), {"start": lambda self: done.append(target(*args))})())
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 50, 80)).save(buffer, "JPEG")
    buffer.seek(0)
    resp = client.post("/handle_upload", data={"photos": (buffer, "fete.jpg"), "name": "Léa"}, content_type="multipart/form-data", headers=SAME)
    assert resp.status_code in (200, 302) and done
    arrived = party.pop_live()
    assert len(arrived) == 1 and arrived[0]["author"] == "Léa" and Path(arrived[0]["path"]).exists()
    assert admin_client.get("/api/party").get_json()["photos"] == 1
    r = admin_client.post("/api/party/stop", headers=SAME).get_json()
    assert r["success"] and not r["active"]
