"""Musique selon l'heure : plages horaires, lancement, respect de la musique lancée à la main, arrêt en fin de plage."""
from datetime import datetime

from utils import music_schedule as ms

SAME = {"Sec-Fetch-Site": "same-origin"}
CONFIG = {"music_schedule": {"enabled": True, "slots": [
    {"start": "07:00", "end": "10:00", "kind": "radio", "value": "https://fip/stream", "label": "FIP"},
    {"start": "22:00", "end": "01:00", "kind": "spotify", "value": "spotify:playlist:abc", "label": "Nuit"}]}}
at = lambda h, m=0: datetime(2026, 10, 12, h, m)


def test_slots():
    assert ms.current(CONFIG, at(8))["label"] == "FIP" and ms.current(CONFIG, at(10)) is None
    assert ms.current(CONFIG, at(0, 30))["label"] == "Nuit"  # plage qui passe minuit
    assert ms.clean_slots([{"start": "25:00", "end": "10:00", "kind": "radio", "value": "x"},
                           {"start": "07:00", "end": "07:00", "kind": "radio", "value": "x"},
                           {"start": "07:00", "end": "08:00", "kind": "file", "value": "../secret.mp3"},
                           {"start": "07:00", "end": "08:00", "kind": "tv", "value": "x"}]) == []


def test_conductor_starts_respects_and_stops():
    c = ms.Conductor()
    assert c.tick(CONFIG, None, at(6, 59)) is None
    decision = c.tick(CONFIG, None, at(7))
    assert decision[0] == "start" and decision[1]["label"] == "FIP"
    c.mark_started(decision[1], "radio", "FIP", at(7))
    assert c.tick(CONFIG, {"source": "radio", "title": "FIP"}, at(8)) is None  # déjà lancée
    assert c.tick(CONFIG, {"source": "radio", "title": "FIP"}, at(10)) == ("stop", "radio")  # fin de plage
    # Une musique lancée à la main n'est ni remplacée ni arrêtée
    c = ms.Conductor()
    assert c.tick(CONFIG, {"source": "airplay", "title": "Ma chanson"}, at(7)) is None
    d = c.tick(CONFIG, None, at(7, 5))
    c.mark_started(d[1], "radio", "FIP", at(7, 5))
    assert c.tick(CONFIG, {"source": "spotify", "title": "Autre"}, at(8)) is None
    assert c.tick(CONFIG, {"source": "spotify", "title": "Autre"}, at(10)) is None
    assert c.tick({"music_schedule": {"enabled": False}}, None, at(7)) is None


def test_schedule_api(admin_client):
    from utils.config_manager import load_config, save_config
    original = dict(load_config())
    try:
        r = admin_client.post("/api/music/schedule", json=dict(CONFIG["music_schedule"]), headers=SAME).get_json()
        assert r["success"] and len(r["slots"]) == 2
        data = admin_client.get("/api/music/schedule").get_json()
        assert data["enabled"] and data["stations"] and isinstance(data["files"], list)
    finally:
        save_config(original)
