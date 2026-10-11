"""Minuteur de sommeil et baisse de la musique pendant les vidéos."""
import json
import time

from utils import music_remote, sleep_timer

SAME = {"Sec-Fetch-Site": "same-origin"}


def test_sleep_timer_fades_and_pauses(monkeypatch):
    volumes, paused = [], []
    monkeypatch.setattr(sleep_timer, "FADE_SECONDS", 0.05)
    monkeypatch.setattr(music_remote, "get_volume", lambda: (60, False))
    monkeypatch.setattr(music_remote, "set_volume", lambda v: volumes.append(round(v)))
    monkeypatch.setattr(music_remote, "pause_everything", lambda: paused.append(True))
    sleep_timer.start(1)
    assert 55 <= sleep_timer.remaining() <= 60
    sleep_timer.cancel()
    assert sleep_timer.remaining() is None
    sleep_timer._expire()
    assert volumes[0] < 60 and volumes[-2] == 0 and volumes[-1] == 60 and paused == [True]  # fondu, pause, volume rétabli


def test_sleep_api(admin_client, monkeypatch):
    monkeypatch.setattr(sleep_timer, "_expire", lambda: None)
    r = admin_client.post("/api/music/sleep", json={"minutes": 30}, headers=SAME).get_json()
    assert r["success"] and 1790 <= r["remaining"] <= 1800
    assert admin_client.get("/api/music/sleep").get_json()["remaining"] > 0
    assert admin_client.post("/api/music/sleep", json={"minutes": 0}, headers=SAME).get_json()["remaining"] is None
    assert admin_client.post("/api/music/sleep", json={"minutes": "x"}, headers=SAME).status_code == 400


def test_duck_and_restore(monkeypatch, tmp_path):
    from utils import radio, spotify
    monkeypatch.setattr(music_remote, "DUCK_FILE", tmp_path / "duck.json")
    calls = []

    def ipc(*command):
        calls.append(command)
        return 80 if command[0] == "get_property" else None
    monkeypatch.setattr(radio, "_ipc", ipc)
    monkeypatch.setattr(radio, "playing", lambda: True)
    monkeypatch.setattr(music_remote, "_players", lambda: [])
    monkeypatch.setattr(spotify, "connected", lambda: False)
    assert music_remote.duck(True, 0.25) == {"radio": 80}
    assert ("set_property", "volume", 20.0) in calls
    assert json.loads((tmp_path / "duck.json").read_text()) == {"radio": 80}
    music_remote.duck(False)
    assert calls[-1] == ("set_property", "volume", 80) and not (tmp_path / "duck.json").exists()
